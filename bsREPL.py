from migen import *
from litex.soc.interconnect.csr import *
from migen.fhdl import *
from bsv_parser import BSVInterface
from functools import partial

class bsREPL(Module):

    def __init__(self, comm=None):
        self._comm = comm
        INTERFACE = """
        interface Ifc_type;
          method Action collatz_submit(Int#(64) n);
          method ActionValue#(Int#(64)) collatz_get();
        endinterface: Ifc_type
        """

        self.interface = BSVInterface(INTERFACE)

        if comm is None:
            self._init_HDL()
        else:
            self._init_REPL()

    def _init_HDL(self):
        # we need a parse of BsTop's type; so we can interface with it.
        # currently we hardcode the collatz interface.
        # currently only support single-arg inputs...!
        # actionmethods = [("Int", 64, "n", "collatz_submit")]
        # actionvaluemethods = [("Int", 64, "collatz_get")]
        self.signals = signals = {}

        self.reset = reset = CSRStorage(1, description="reset DUT on write", write_from_dev=True)
        self.csrs = csrs = {"reset": self.reset}

        rst_n = Signal()
        self.reset_count = reset_count = Signal(4)

        # invert the reset signal for bsv (active low) and mix in the host-triggered reset
        self.comb += [rst_n.eq( (ResetSignal() | (reset_count > 0)) ^ 1 )]

        # reset pulse generator; hold in reset for 16cycles when the host writes a 1
        self.sync += [
            If(reset.storage == 1,
               reset.storage.eq(0),
               self.reset_count.eq(2**4-1)
              ),
            If(reset_count > 0, reset_count.eq(reset_count-1)), # countdown
            ]

        self.signals = connections = []

        for type, width, arg_name, method_name, in self.interface.actionmethods:
            # generate CSRs to interface. inputs call action methods.
            # ready, enable, ack. When calling a method, we wait for ready
            # set value, and pulse enable before returning.
            value = CSRStorage(width,
                               description=f"input {method_name} {arg_name} value CSR",
                               name=f"{method_name}_{arg_name}_value_csr",
                               write_from_dev=True)
            csrs[f"{method_name}_{arg_name}_value_csr"] = value

            # set to 0 by dev: waiting,
            # set to 1 by host: attempt write,
            # set to 0 by dev: write commited
            trigger = CSRStorage(1, description=f"input {method_name} trigger CSR",
                                 name=f"{method_name}_trigger_csr",
                                 write_from_dev=True)
            csrs[f"{method_name}_trigger_csr"] = trigger

            status = CSRStatus(4, description=f"input {method_name} internal status CSR",
                                 name=f"{method_name}_status_csr")
            csrs[f"{method_name}_status_csr"] = status

            # we need to pulse enable when we have new data, but we can't do
            # single-cycle pulse from Python - use a simple edge detector here.
            enable_edge = Signal(1, reset=0)
            signals[f"{method_name}_enable_edge"] = enable_edge
            self.sync += [status.status[0].eq(enable_edge)]
            ready_to_write = Signal(1)
            signals[f"{method_name}_ready_to_write"] = ready_to_write
            self.sync += [status.status[1].eq(ready_to_write)]
            value_sig = Signal(width, reset=0)
            signals[f"{method_name}_value_sig"] = value_sig
            self.sync += [status.status[2].eq(value_sig)]

            # keep in top bit
            self.sync += [status.status[3].eq(rst_n)]

            action_fsm = FSM(reset_state="RESET")
            self.submodules += action_fsm

            action_fsm.act("RESET",
                           NextValue(value.storage, 0),
                           NextValue(trigger.storage, 0),
                           NextValue(enable_edge, 0),
                           NextState("WAIT"),
                          )
            action_fsm.act("WAIT",
                           # does not progress trigger to 0 until ready_to_write goes high
                           If(trigger.storage & ready_to_write,
                             NextValue(value_sig, value.storage),
                             NextState("SEND")),
                          )
            action_fsm.act("SEND",
                           NextValue(enable_edge, 1),
                           NextValue(value_sig, value.storage),
                           NextState("RESET")
                          )

            connections += [Instance.Input(f"{method_name}_{arg_name}", value_sig),
                            Instance.Input(f"EN_{method_name}", enable_edge),
                            Instance.Output(f"RDY_{method_name}", ready_to_write)]

        for type, width, method_name in self.interface.actionvaluemethods:
            # actionvalue methods are a way of statefully returning a value
            # from a module. They have vale, EN, and RDY signals.
            # The module will hold RDY high if the methods can be called.
            # To call the method, send EN high for 1 cycle. Next cycle,
            # value will hold the data. This needs to be copied to the
            # CSR from verilog.
            value = CSRStatus(width,
                              description=f"output {method_name} value CSR",
                              name=f"{method_name}_value_csr")
            csrs[f"{method_name}_value_csr"] = value
            ack = CSRStorage(1,
                             description=f"output {method_name} ack read csr",
                             name=f"{method_name}_ack_csr",
                             reset=1, # when we start there was no prior value, so we say it's been ack'ed
                             write_from_dev=True)
            csrs[f"{method_name}_ack_csr"] = ack

            status = CSRStatus(4,
                              description=f"output {method_name} status CSR",
                              name=f"{method_name}_status_csr")
            csrs[f"{method_name}_status_csr"] = status


            value_sig = Signal(width)
            ready_sig = Signal(1)
            enable_sig = Signal(1)
            signals[f"{method_name}_value_sig"] = value_sig
            signals[f"{method_name}_enable_edge"] = enable_sig
            signals[f"{method_name}_ready_to_read"] = ready_sig
            self.sync += [status.status[0].eq(ready_sig),
                          status.status[1].eq(enable_sig),
                          status.status[3].eq(rst_n)]

            # when enable_toggle goes high, we need to pulse enable,
            # then copy value_sig into value.status.
            readout_fsm = FSM(reset_state="RESET")
            self.submodules += readout_fsm
            readout_fsm.act("RESET",
                            NextValue(value.status, 0),
                            NextValue(enable_sig, 0),
                            NextState("WAIT")
                           )

            readout_fsm.act("WAIT",
                            If(ack.storage == 1 and ready_sig == 1, # value to read and the prior value has been ack'ed
                               NextValue(enable_sig, 1),
                               NextValue(ack.storage, 0),
                               NextState("RESET"),
                             )
                           )

            self.sync += [value.status.eq(value_sig)]

            connections += [Instance.Output(f"{method_name}", value_sig),
                            Instance.Input(f"EN_{method_name}", enable_sig),
                            Instance.Output(f"RDY_{method_name}", ready_sig)]

        # Add the user module
        self.specials += Instance("mkCollatzServer",
                                  Instance.Input("CLK", ClockSignal()),
                                  Instance.Input("RST_N", rst_n),
                                  *connections)

        for name, csr in csrs.items():
            print(name, csr)
            self.__setattr__(name, csr)

    def _init_REPL(self):
        for type, width, arg_name, method_name, in self.interface.actionmethods:
            fn = partial(self._action_call, modname="bsREPL", methodname=method_name)
            self.__setattr__(method_name, fn)

        for type, width, method_name in self.interface.actionvaluemethods:
            fn = partial(self._action_value_return, modname="bsREPL", methodname=method_name)
            self.__setattr__(method_name, fn)

    def _action_call(self, modname, methodname, **kwargs):
        module = self._comm.regs
        trigger = getattr(module, f"{modname}_{methodname}_trigger_csr")

        # get each register for the called args
        value_regs = {k : getattr(module, f"{modname}_{methodname}_{k}_value_csr")
                      for k in kwargs.keys()}

        while trigger.read() != 0:
            # make sure any prior submission is accepted
            pass

        for k, v in kwargs.items():
            value_regs[k].write(v)
        trigger.write(1)

        while trigger.read() == 1:
            # wait for ack
            pass

    def _action_value_return(self, modname, methodname):
        module = self._comm.regs
        ack = getattr(module, f"{modname}_{methodname}_ack_csr")
        value = getattr(module, f"{modname}_{methodname}_value_csr")
        while ack.read() == 1: # wait for a valid, new value
            pass
        v = value.read()
        ack.write(1) # advance the FIFO
        return v

    def status(self):
        dev = self._dev
        print(f"""
        value in {self._comm.regs.bsREPL_collatz_submit_value_csr}
        trgger {self._comm.regs.bsREPL_collatz_submit_trigger_csr}
        fsm state {bin(self._comm.regs.bsREPL_collatz_submit_status_csr)}
        value out {self._comm.regs.bsREPL_collatz_get_value_csr}
        ack out {self._comm.regs.bsREPL_collatz_get_ack_csr}
        out status {bin(self._comm.regs.bsREPL_collatz_get_status_csr)}""")

    def get_csrs(self):
        return list(self.csrs.values())


if __name__ == "__main__":
    from device import dev, comm
    collatz_repl = bsREPL(comm)

    def bs_collatz(n):
        collatz_repl.collatz_submit(n=n)
        return collatz_repl.collatz_get()

    def collatz(n):
        cnt = 0
        while n != 1:
            if n % 2 == 0:
                n = n/2
            else:
                n = 3*n + 1
            cnt += 1
        return cnt

    def test_1(dev):
        dev.bsREPL_reset = 1
        for n in range(5, 10000):
            print(".", end="", flush=True)
            if bs_collatz(n) != collatz(n):
                print(n)
                status()

    print(dev)
    test_1(dev)
    print("passed")

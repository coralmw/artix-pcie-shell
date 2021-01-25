from litex.tools.remote.comm_pcie import CommPCIe
from pprint import pprint as p
import pint
ureg = pint.UnitRegistry()

def vp(i):
    p(vars(i))


bar = "03:00.0"
comm = CommPCIe(bar, debug=False, csr_csv="csr.csv")
comm.enable(); comm.open()


# import code; from pprint import pprint as p; code.InteractiveConsole(locals=dict(globals(), **locals())).interact()

class FilteredDevice():
    
    def __init__(self, comm):
        self.comm = comm

    def __getattr__(self, attr):
        return self.comm.regs.__getattr__(attr).read()
    
    @property
    def ident(self):
        return self.comm.read_str(self.comm.bases.identifier_mem)
    
    @property
    def temp(self):
        val = self.comm.regs.xadc_temperature.read()
        t = ureg.Quantity((val*503.975/4096 - 273.15), ureg.degC)
        return t
    
    def __getattr__(self, key):
        return getattr(self.comm.regs, key).read()
        
    def __setattr__(self, key, value):
        if key == "comm":
            object.__setattr__(self, key, value)
            return
        return getattr(self.comm.regs, key).write(value)

dev = FilteredDevice(comm)

if __name__ == "__main__":
    vp(comm)
    print(dev.ident)
    print(dev.temp)
    import IPython
    IPython.embed()
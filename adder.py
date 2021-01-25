from migen import *
from litex.soc.interconnect.csr import *
from migen.fhdl import *

class CustomAdder(Module, AutoCSR):
    def __init__(self):
        self.a = a = CSRStorage(32, description="""a in.""")
        self.b = b = CSRStorage(32, description="""b in.""")
        self.c = c = CSRStatus(32, description="""result out.""")

        # # if a or b updates, write to c
        # self.sync += [If(a.re | b.re,
        #                     c.status.eq(a.storage + b.storage)
        #                  )
        # ]
        self.specials += Instance("mkBsAdder",
                                  Instance.Input("CLK", ClockSignal()),
                                  Instance.Input("RST_N", ResetSignal()),
                                  Instance.Input("reply_x", a.storage),
                                  Instance.Input("reply_y", b.storage),
                                  Instance.Output("reply", c.status))


import unittest

class TestCustomAdder(unittest.TestCase):

    def setUp(self):
        from device import dev
        self.dev = dev

    def test_add(self):
        for a in range(2**8):
            for b in range(2**8):
                self.dev.cadd_a = a
                self.dev.cadd_b = b
                self.assertEqual(self.dev.cadd_c, a+b)

if __name__ == '__main__':
    unittest.main()

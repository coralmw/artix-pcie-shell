package BsAdder;

(* synthesize *)
module mkTb(Empty);

 Ifc_type ifc <- mkBsAdder;

 rule run;
   $display("hello world, reply %0d", ifc.reply(1,2));
   $finish(0);
 endrule

endmodule: mkTb

interface Ifc_type;
 method int reply(Int#(32) x, Int#(32) y);
endinterface: Ifc_type

(* synthesize *)
module mkBsAdder(Ifc_type);
 method reply(Int#(32) x, Int#(32) y);
   return x+y;
 endmethod

endmodule: mkBsAdder

endpackage: BsAdder

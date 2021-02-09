.PHONY: setup-shell
setup-shell:
	@echo "source /tools/Xilinx/Vivado/2018.3/settings64.sh &&"
	@echo "source venv/bin/activate &&"
	@echo "export PATH=\$$PATH:`pwd`/upstream/riscv64-unknown-elf-gcc-8.3.0-2019.08.0-x86_64-linux-ubuntu14/bin"
	@echo "export PATH=\$$PATH:~/upstream/bsc/inst/bin"

clean:
	rm -rf build/*

# -reset-prefix "RESET_P" -D BSV_POSITIVE_RESET
build/mkCollatzServer.v: CollatzServer.bsv
	bsc -verilog -u -g mkCollatzServer -vdir build $<

# build a top module first.
build/BsTop.v: BsTop.bsv
	bsc -verilog -u -g BsTop -vdir build $<


design: upstream/litex-boards/litex_boards/targets/acorn_cle_215.py build/mkBsAdder.v build/mkCollatzServer.v
	python acorn_cle_215.py --uart-name=crossover --with-pcie --build --driver --csr-csv "csr.csv" --output-dir build

csr.csv:
	python acorn_cle_215.py --uart-name=crossover --with-pcie --csr-csv "csr.csv" --output-dir build

# this can be built wherever
.PHONY: design-flash
design-flash: build/mkCollatzServer.v
	python acorn_cle_215.py --uart-name=crossover --with-pcie --build --flash --driver --csr-csv "csr.csv" --output-dir build
	make driver
	cd build/driver/user && make all
	sudo chmod 777 /sys/bus/pci/devices/0000:03:00.0/*

shell:
	python device.py

info:
	build/driver/user/litepcie_util info

.ONESHELL:
driver: build/driver/kernel/csr.h
	cd build/driver/kernel
	make clean
	make all
	-sudo rmmod litepcie
	# -sudo ../../../hot_reset.sh `lspci -nn | grep Xilinx | cut -d" " -f1`
	-sudo ../../../hot_reset.sh 03:00.0
	-sudo ./init.sh

.ONESHELL:
test-driver:
	cd build/driver/user
	make all
	sudo ./litepcie_util info
	sudo ./litepcie_util scratch_test
	sudo ./litepcie_util dma_test
	sudo ./litepcie_util uart_test

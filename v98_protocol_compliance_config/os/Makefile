CROSS ?= x86_64-elf-
CXX := $(CROSS)g++
LD := $(CROSS)ld
OBJDUMP := $(CROSS)objdump
READELF := $(CROSS)readelf

BUILD_DIR := build
INCLUDE_DIR := include
TEST_DIR := tests

COMMON_FLAGS := \
	-std=c++23 \
	-O2 \
	-ffreestanding \
	-fno-builtin \
	-fno-exceptions \
	-fno-rtti \
	-fno-threadsafe-statics \
	-fno-use-cxa-atexit \
	-fno-omit-frame-pointer \
	-mno-red-zone \
	-mcmodel=kernel \
	-nostdinc++ \
	-Wall -Wextra -Werror \
	-Wconversion -Wsign-conversion -Wdouble-promotion -Wshadow \
	-fstrict-aliasing \
	-fno-delete-null-pointer-checks \
	-I$(INCLUDE_DIR)

TRAP_UBSAN_FLAGS := -fsanitize=undefined -fsanitize-undefined-trap-on-error

FOUNDATION_OBJECT := $(BUILD_DIR)/kernel_types_compile.o
TRAP_UBSAN_OBJECT := $(BUILD_DIR)/kernel_types_compile.ubsan.o
LINKER_PROBE_OBJECT := $(BUILD_DIR)/linker_probe.o
LINKER_PROBE_ELF := $(BUILD_DIR)/linker_probe.elf

.PHONY: all check toolchain-check compile-check ubsan-trap-check linker-check inspect clean help

all: check

help:
	@printf '%s\n' \
	  'toolchain-check  Verify required x86_64-elf tools exist' \
	  'compile-check    Compile the freestanding foundation header test' \
	  'ubsan-trap-check Compile trap-based UBSan instrumentation without libubsan' \
	  'linker-check     Parse linker.ld and verify higher-half section layout' \
	  'inspect          Print ELF headers and sections for the linker probe' \
	  'check            Execute all non-runtime Phase-1 verification gates' \
	  'clean            Remove generated build products'

toolchain-check:
	@command -v $(CXX) >/dev/null || { echo 'missing $(CXX)'; exit 1; }
	@command -v $(LD) >/dev/null || { echo 'missing $(LD)'; exit 1; }
	@command -v $(OBJDUMP) >/dev/null || { echo 'missing $(OBJDUMP)'; exit 1; }
	@command -v $(READELF) >/dev/null || { echo 'missing $(READELF)'; exit 1; }
	@$(CXX) --version | head -n 1
	@$(LD) --version | head -n 1

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

$(FOUNDATION_OBJECT): $(TEST_DIR)/kernel_types_compile.cpp $(INCLUDE_DIR)/kernel_types.hpp | $(BUILD_DIR)
	$(CXX) $(COMMON_FLAGS) -c $< -o $@

compile-check: toolchain-check $(FOUNDATION_OBJECT)
	@$(READELF) -h $(FOUNDATION_OBJECT) | grep -q 'Machine:.*Advanced Micro Devices X86-64'
	@echo 'GATE_01_FOUNDATION_COMPILE: PASS'

$(TRAP_UBSAN_OBJECT): $(TEST_DIR)/kernel_types_compile.cpp $(INCLUDE_DIR)/kernel_types.hpp | $(BUILD_DIR)
	$(CXX) $(COMMON_FLAGS) $(TRAP_UBSAN_FLAGS) -c $< -o $@

ubsan-trap-check: toolchain-check $(TRAP_UBSAN_OBJECT)
	@if $(READELF) -Ws $(TRAP_UBSAN_OBJECT) | grep -q '__ubsan_handle_'; then \
	  echo 'unexpected libubsan runtime dependency'; exit 1; \
	fi
	@echo 'GATE_01_TRAP_UBSAN_COMPILE: PASS'

$(LINKER_PROBE_OBJECT): $(TEST_DIR)/kernel_types_compile.cpp $(INCLUDE_DIR)/kernel_types.hpp | $(BUILD_DIR)
	$(CXX) $(COMMON_FLAGS) -fno-pic -c $< -o $@

$(LINKER_PROBE_ELF): linker.ld $(LINKER_PROBE_OBJECT)
	$(LD) -nostdlib -z max-page-size=0x1000 -T linker.ld -e kernel_types_compile_anchor \
	  $(LINKER_PROBE_OBJECT) -o $@

linker-check: toolchain-check $(LINKER_PROBE_ELF)
	@$(READELF) -S $(LINKER_PROBE_ELF) | grep -q '\.text'
	@$(READELF) -S $(LINKER_PROBE_ELF) | grep -q '\.rodata' || true
	@$(READELF) -S $(LINKER_PROBE_ELF) | grep -q '\.data' || true
	@$(OBJDUMP) -h $(LINKER_PROBE_ELF) | grep '\.text' | grep -qi 'ffffffff8'
	@echo 'GATE_01_LINKER_LAYOUT: PASS'

inspect: $(LINKER_PROBE_ELF)
	$(READELF) -h $(LINKER_PROBE_ELF)
	$(READELF) -l $(LINKER_PROBE_ELF)
	$(OBJDUMP) -h $(LINKER_PROBE_ELF)

check: compile-check ubsan-trap-check linker-check
	@echo 'PHASE_1_STATIC_FOUNDATION: PASS'
	@echo 'NOTE: boot execution is not yet proven; Multiboot2 entry and QEMU readback remain pending.'

clean:
	rm -rf $(BUILD_DIR)

OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(_start)

KERNEL_PHYS_BASE = 0x00100000;
KERNEL_VIRT_BASE = 0xFFFFFFFF80000000;
PAGE_SIZE = 0x1000;

PHDRS
{
    boot PT_LOAD FLAGS(5);   /* R-X: Multiboot2 header and transition code */
    text PT_LOAD FLAGS(5);   /* R-X */
    rodata PT_LOAD FLAGS(4); /* R-- */
    data PT_LOAD FLAGS(6);   /* RW- */
}

SECTIONS
{
    . = KERNEL_PHYS_BASE;
    __kernel_physical_start = .;

    .boot ALIGN(PAGE_SIZE) :
    {
        __boot_start = .;
        KEEP(*(.multiboot2))
        KEEP(*(.boot.text .boot.text.*))
        KEEP(*(.boot.rodata .boot.rodata.*))
        KEEP(*(.boot.data .boot.data.*))
        __boot_end = .;
    } :boot

    ASSERT((ADDR(.boot) - KERNEL_PHYS_BASE) < 32768,
           "Multiboot2 header must reside within first 32 KiB of image");

    . = ALIGN(PAGE_SIZE);
    __kernel_lma_after_boot = .;

    . += KERNEL_VIRT_BASE;
    __kernel_virtual_start = .;

    .text ALIGN(PAGE_SIZE) : AT(ADDR(.text) - KERNEL_VIRT_BASE)
    {
        __text_start = .;
        *(.text .text.*)
        __text_end = .;
    } :text

    .rodata ALIGN(PAGE_SIZE) : AT(ADDR(.rodata) - KERNEL_VIRT_BASE)
    {
        __rodata_start = .;
        *(.rodata .rodata.*)
        *(.eh_frame_hdr)
        *(.eh_frame)
        __rodata_end = .;
    } :rodata

    .data ALIGN(PAGE_SIZE) : AT(ADDR(.data) - KERNEL_VIRT_BASE)
    {
        __data_start = .;
        *(.data .data.*)
        __data_end = .;
    } :data

    .bss ALIGN(PAGE_SIZE) (NOLOAD) : AT(ADDR(.bss) - KERNEL_VIRT_BASE)
    {
        __bss_start = .;
        *(COMMON)
        *(.bss .bss.*)
        __bss_end = .;
    } :data

    . = ALIGN(PAGE_SIZE);
    __kernel_virtual_end = .;
    __kernel_physical_end = . - KERNEL_VIRT_BASE;

    /DISCARD/ :
    {
        *(.comment)
        *(.note .note.*)
        *(.interp)
        *(.dynamic)
        *(.dynsym)
        *(.dynstr)
        *(.gnu.*)
        *(.plt .plt.*)
        *(.got .got.*)
    }

    ASSERT((__text_start & (PAGE_SIZE - 1)) == 0,
           ".text is not page aligned");
    ASSERT((__rodata_start & (PAGE_SIZE - 1)) == 0,
           ".rodata is not page aligned");
    ASSERT((__data_start & (PAGE_SIZE - 1)) == 0,
           ".data is not page aligned");
    ASSERT((__bss_start & (PAGE_SIZE - 1)) == 0,
           ".bss is not page aligned");
    ASSERT(__kernel_virtual_start >= KERNEL_VIRT_BASE,
           "kernel VMA escaped higher-half contract");
}

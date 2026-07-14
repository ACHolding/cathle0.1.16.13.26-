#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cathle 0.1.1 — N64 emulator monolith (PJ64-Legacy integrated)
Engine: cathle
Single-file Python 3.14 — Tkinter (PIL optional for framebuffer)
"""
from __future__ import annotations
import base64, math, os, platform, struct, sys, time, random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
import threading

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_ROM_DIR = os.path.join(_SCRIPT_DIR, "Roms")
_ROM_SCAN_MAX_FILES = 512
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = filedialog = messagebox = ttk = None

APP_NAME = "cathle 0.1.1"
VERSION = "0.1.1"; ENGINE_NAME = "cathle"; PYTHON_TARGET = "3.14"
WINDOW_TITLE = "cathle 0.1.1"
ROM_EXTENSIONS = (".z64", ".v64", ".n64", ".rom", ".bin")
ROM_BROWSER_COLUMNS = (("file_name","File Name",220),("internal_name","Internal Name",180),("good_name","Good Name",200),("status","Status",90),("rom_size","Rom Size",90))

CATHLE_WIN_GRAY = CATHLE_WIN_FACE = CATHLE_BTN_FACE = "#c0c0c0"
CATHLE_BTN_HIGHLIGHT = "#ffffff"; CATHLE_BTN_SHADOW = "#808080"
CATHLE_PANEL_WHITE = "#ffffff"; CATHLE_TEXT = "#000000"; CATHLE_SPLASH_GRAY = "#808080"
CATHLE_VIEWPORT_BORDER = "#808080"; CATHLE_LIST_SEL_BG = "#000080"; CATHLE_LIST_SEL_FG = "#ffffff"
BG_COLOR, PANEL_COLOR, TEXT_COLOR = CATHLE_WIN_GRAY, CATHLE_BTN_FACE, CATHLE_TEXT
ACCENT_BLUE, TERMINAL_GREEN, STATUS_RED, WHITE = CATHLE_TEXT, "#008000", "#800000", CATHLE_PANEL_WHITE
def _cathle_ui_fonts():
    if platform.system() == "Darwin": return ("Tahoma",11),("Courier New",11),("Tahoma",11,"bold")
    if platform.system() == "Windows": return ("MS Sans Serif",8),("Courier New",9),("MS Sans Serif",8,"bold")
    return ("TkDefaultFont",9),("Courier New",9),("TkDefaultFont",9,"bold")
UI_FONT, UI_FONT_MONO, UI_FONT_BOLD = _cathle_ui_fonts()

RDRAM_SIZE = 8*1024*1024; RDRAM_SIZE_4MB = 4*1024*1024
RSP_DMEM_SIZE = 0x1000; RSP_IMEM_SIZE = 0x1000; PIF_RAM_SIZE = 0x40
EEPROM_4K_SIZE = 0x200; EEPROM_16K_SIZE = 0x800; SRAM_SIZE = 0x8000; FLASHRAM_SIZE = 0x10000
MASK_8 = 0xFF; MASK_16 = 0xFFFF; MASK_32 = 0xFFFFFFFF; MASK_64 = 0xFFFFFFFFFFFFFFFF
def u8(v): return v & MASK_8
def u16(v): return v & MASK_16
def u32(v): return v & MASK_32
def u64(v): return v & MASK_64
def sign8(v): v &= MASK_8; return v - 0x100 if v & 0x80 else v
def sign16(v): v &= MASK_16; return v - 0x10000 if v & 0x8000 else v
def sign32(v): v &= MASK_32; return v - 0x100000000 if v & 0x80000000 else v
def sign64(v): v &= MASK_64; return v - 0x10000000000000000 if v & 0x8000000000000000 else v
def sx8_to_64(v): return u64(sign8(v))
def sx16_to_64(v): return u64(sign16(v))
def sx32_to_64(v): return u64(sign32(v))
def be32(data, off):
    if off < 0 or off + 3 >= len(data): return 0
    return struct.unpack_from(">I", data, off)[0]
def put_be32(data, off, val):
    if off < 0 or off + 3 >= len(data): return
    struct.pack_into(">I", data, off, val & MASK_32)
def be64(data, off):
    if off < 0 or off + 7 >= len(data): return 0
    return struct.unpack_from(">Q", data, off)[0]
def put_be64(data, off, val):
    if off < 0 or off + 7 >= len(data): return
    struct.pack_into(">Q", data, off, val & MASK_64)
def f32_to_bits(v): return struct.unpack(">I", struct.pack(">f", float(v)))[0]
def bits_to_f32(v): return struct.unpack(">f", struct.pack(">I", v & MASK_32))[0]
def f64_to_bits(v): return struct.unpack(">Q", struct.pack(">d", float(v)))[0]
def bits_to_f64(v): return struct.unpack(">d", struct.pack(">Q", v & MASK_64))[0]

# ── PJ64-Legacy Register Map ──
SP_MEM_ADDR=0x04040000; SP_DRAM_ADDR=0x04040004; SP_RD_LEN=0x04040008; SP_WR_LEN=0x0404000C
SP_STATUS=0x04040010; SP_DMA_FULL=0x04040014; SP_DMA_BUSY=0x04040018; SP_SEMAPHORE=0x0404001C
SP_PC=0x04080000; SP_IBIST=0x04080004
SP_STATUS_HALT=0x0001; SP_STATUS_BROKE=0x0002; SP_STATUS_DMA_BUSY=0x0004; SP_STATUS_DMA_FULL=0x0008
SP_STATUS_IO_FULL=0x0010; SP_STATUS_SSTEP=0x0020; SP_STATUS_INTR_BREAK=0x0040
SP_CLR_HALT=0x0001; SP_SET_HALT=0x0002; SP_CLR_BROKE=0x0004; SP_CLR_INTR=0x0008; SP_SET_INTR=0x0010
SP_CLR_SSTEP=0x0020; SP_SET_SSTEP=0x0040; SP_CLR_INTR_BREAK=0x0080; SP_SET_INTR_BREAK=0x0100
SP_CLR_SIG0=0x0200; SP_SET_SIG0=0x0400; SP_CLR_SIG1=0x0800; SP_SET_SIG1=0x1000
SP_CLR_SIG2=0x2000; SP_SET_SIG2=0x4000; SP_CLR_SIG3=0x00010000; SP_SET_SIG3=0x00020000
SP_CLR_SIG4=0x00040000; SP_SET_SIG4=0x00080000; SP_CLR_SIG5=0x00100000; SP_SET_SIG5=0x00200000
SP_CLR_SIG6=0x00400000; SP_SET_SIG6=0x00800000; SP_CLR_SIG7=0x01000000; SP_SET_SIG7=0x02000000
DPC_START=0x04100000; DPC_END=0x04100004; DPC_CURRENT=0x04100008; DPC_STATUS=0x0410000C
DPC_CLOCK=0x04100010; DPC_BUFBUSY=0x04100014; DPC_PIPEBUSY=0x04100018; DPC_TMEM=0x0410001C
DPC_STATUS_XBUS_DMEM_DMA=0x0001; DPC_STATUS_FREEZE=0x0002; DPC_STATUS_FLUSH=0x0004
DPC_CLR_XBUS_DMEM_DMA=0x0001; DPC_SET_XBUS_DMEM_DMA=0x0002; DPC_CLR_FREEZE=0x0004; DPC_SET_FREEZE=0x0008
DPC_CLR_FLUSH=0x0010; DPC_SET_FLUSH=0x0020
DPS_TBIST=0x04200000; DPS_TEST_MODE=0x04200004; DPS_BUFTEST=0x04200008; DPS_DETAIL=0x0420000C
MI_MODE=0x04300000; MI_VERSION=0x04300004; MI_INTR=0x04300008; MI_INTR_MASK=0x0430000C
MI_MODE_INIT=0x0001; MI_MODE_EBUS=0x0002; MI_MODE_RDRAM=0x0004
MI_CLR_INIT=0x0001; MI_SET_INIT=0x0002; MI_CLR_EBUS=0x0004; MI_SET_EBUS=0x0008; MI_CLR_DP_INTR=0x0010
MI_CLR_RDRAM=0x0020; MI_SET_RDRAM=0x0040
MI_INTR_SP=0x01; MI_INTR_SI=0x02; MI_INTR_AI=0x04; MI_INTR_VI=0x08; MI_INTR_PI=0x10; MI_INTR_DP=0x20
MI_INTR_MASK_CLR_SP=0x0001; MI_INTR_MASK_SET_SP=0x0002; MI_INTR_MASK_CLR_SI=0x0004; MI_INTR_MASK_SET_SI=0x0008
MI_INTR_MASK_CLR_AI=0x0010; MI_INTR_MASK_SET_AI=0x0020; MI_INTR_MASK_CLR_VI=0x0040; MI_INTR_MASK_SET_VI=0x0080
MI_INTR_MASK_CLR_PI=0x0100; MI_INTR_MASK_SET_PI=0x0200; MI_INTR_MASK_CLR_DP=0x0400; MI_INTR_MASK_SET_DP=0x0800
VI_STATUS=0x04400000; VI_ORIGIN=0x04400004; VI_WIDTH=0x04400008; VI_INTR=0x0440000C
VI_V_CURRENT=0x04400010; VI_BURST=0x04400014; VI_V_SYNC=0x04400018; VI_H_SYNC=0x0440001C
VI_LEAP=0x04400020; VI_H_START=0x04400024; VI_V_START=0x04400028; VI_V_BURST=0x0440002C
VI_X_SCALE=0x04400030; VI_Y_SCALE=0x04400034
AI_DRAM_ADDR=0x04500000; AI_LEN=0x04500004; AI_CONTROL=0x04500008; AI_STATUS=0x0450000C
AI_DACRATE=0x04500010; AI_BITRATE=0x04500014
AI_STATUS_FIFO_FULL=0x40000000; AI_STATUS_DMA_BUSY=0x80000000
PI_DRAM_ADDR=0x04600000; PI_CART_ADDR=0x04600004; PI_RD_LEN=0x04600008; PI_WR_LEN=0x0460000C
PI_STATUS=0x04600010; PI_DOM1_LAT=0x04600014; PI_DOM1_PWD=0x04600018; PI_DOM1_PGS=0x0460001C
PI_DOM1_RLS=0x04600020; PI_DOM2_LAT=0x04600024; PI_DOM2_PWD=0x04600028; PI_DOM2_PGS=0x0460002C
PI_DOM2_RLS=0x04600030; PI_STATUS_DMA_BUSY=0x0001
RI_MODE=0x04700000; RI_CONFIG=0x04700004; RI_CURRENT_LOAD=0x04700008; RI_SELECT=0x0470000C
RI_REFRESH=0x04700010; RI_LATENCY=0x04700014; RI_RERROR=0x04700018; RI_WERROR=0x0470001C
SI_DRAM_ADDR=0x04800000; SI_PIF_ADDR_RD=0x04800004; SI_PIF_ADDR_WR=0x04800010; SI_STATUS=0x04800018
SI_STATUS_INTERRUPT=0x1000; SI_STATUS_DMA_BUSY=0x2000

CP0_INDEX=0; CP0_RANDOM=1; CP0_ENTRYLO0=2; CP0_ENTRYLO1=3; CP0_CONTEXT=4; CP0_PAGEMASK=5; CP0_WIRED=6
CP0_BADVADDR=8; CP0_COUNT=9; CP0_ENTRYHI=10; CP0_COMPARE=11; CP0_STATUS=12; CP0_CAUSE=13; CP0_EPC=14
CP0_PRID=15; CP0_CONFIG=16; CP0_LLADDR=17; CP0_ERROREPC=30
STATUS_FR=0x02000000; STATUS_IE=0x0001; STATUS_EXL=0x0002; STATUS_ERL=0x0004; STATUS_BEV=0x00400000; STATUS_CU1=0x20000000
FCR31_COND_BIT=23
FCR31_CAUSE_INEXACT=0x01; FCR31_CAUSE_UNDERFLOW=0x02; FCR31_CAUSE_OVERFLOW=0x04; FCR31_CAUSE_DIVBYZERO=0x08; FCR31_CAUSE_INVALID=0x10

# ── PJ64-Legacy CIC chip detection ──
CIC_NUS_6101,CIC_NUS_6102,CIC_NUS_6103,CIC_NUS_6105,CIC_NUS_6106 = 0,1,2,3,4
CIC_NUS_5167,CIC_NUS_8303,CIC_NUS_8401,CIC_NUS_DDUS,CIC_NUS_XENO = 5,6,7,8,9
SAVE_AUTO=0; SAVE_EEPROM_4K=1; SAVE_EEPROM_16K=2; SAVE_SRAM=3; SAVE_FLASHRAM=4
REGION_NTSC=0; REGION_PAL=1

def get_cic_chip_id(rom):
    if len(rom) < 0x40: return CIC_NUS_6102
    crc1, crc2 = be32(rom,0x10), be32(rom,0x14)
    country = rom[0x3E]
    pal = 0x50 if country in (0x44,0x46,0x49,0x50,0x53,0x55,0x58,0x59) else 0x00
    if country in (0x37,0x38,0x41,0x45,0x4A) or pal:
        val = crc1 ^ crc2
        if val == 0x479F1185: return CIC_NUS_6101
        if val == 0x48C8987D: return CIC_NUS_6102
        if val == 0x185879EB: return CIC_NUS_6103
        if val == 0xECBBAB3E: return CIC_NUS_6105
        if val == 0x2E24BB3E: return CIC_NUS_6106
    return CIC_NUS_6102

def recalculate_crcs(data):
    CRC_SRC_SIZE = 0x00101000
    if len(data) < 0x1000: return 0, 0
    chip = get_cic_chip_id(data)
    seeds = {CIC_NUS_6101: 0xF8CA4DDC, CIC_NUS_6102: 0xF8CA4DDC, CIC_NUS_6103: 0xA3886759,
             CIC_NUS_6105: 0xDF26F436, CIC_NUS_6106: 0x1FEA617A}
    seed = seeds.get(chip, 0xF8CA4DDC)
    t1 = t2 = t3 = t4 = t5 = t6 = seed
    ds = len(data)
    limit = min(CRC_SRC_SIZE, ds)
    is_6105 = chip == CIC_NUS_6105
    for i in range(0x1000, limit, 4):
        d = be32(data, i) if i + 3 < ds else 0
        if (t6 + d) < t6: t4 += 1
        t6 = u32(t6 + d); t3 ^= d
        shift = d & 0x1F
        r = (d << shift) | (d >> (32 - shift)) if shift else d
        t5 = u32(t5 + r)
        if t2 > d: t2 ^= r
        else: t2 ^= t6 ^ d
        if is_6105:
            jd = be32(data, 0x0750 + (i & 0xFF)) if 0x0753 + (i & 0xFF) < ds else 0
            t1 = u32(t1 + (jd ^ d))
        else:
            t1 = u32(t1 + (t5 ^ d))
    if chip == CIC_NUS_6103: crc0 = u32((t6 ^ t4) + t3); crc1 = u32((t5 ^ t2) + t1)
    elif chip == CIC_NUS_6106: crc0 = u32((t6 * t4) + t3); crc1 = u32((t5 * t2) + t1)
    else: crc0 = u32(t6 ^ t4 ^ t3); crc1 = u32(t5 ^ t2 ^ t1)
    return crc0, crc1

Z64_MAGIC = b"\x80\x37\x12\x40"; V64_MAGIC = b"\x37\x80\x40\x12"; N64_LE_MAGIC = b"\x40\x12\x37\x80"
_CART_SIGS = (Z64_MAGIC, V64_MAGIC, N64_LE_MAGIC)

def strip_documentation_header(data):
    if len(data) < 4: return
    if data[0:4] in _CART_SIGS: return
    cap = min(len(data), 16 * 1024 * 1024)
    for off in (4096, 2048, 512):
        if off + 4 <= cap and data[off:off + 4] in _CART_SIGS:
            del data[:off]; return

def apply_cart_header_defaults(data):
    if len(data)<0x40: data.extend(b"\x00"*(0x40-len(data)))
    if data[0:4] not in _CART_SIGS or data[0:4]!=Z64_MAGIC: return
    if be32(data,0x04)==0: put_be32(data,0x04,0x00000F48)
    boot=be32(data,0x08)
    if boot==0 or boot==MASK_32: put_be32(data,0x08,0x80000400)
    if be32(data,0x0C)==0: put_be32(data,0x0C,0x0000144B)
    title=data[0x20:0x34]
    if not any(title): data[0x20:0x34]=b"Ultra 64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"[:20].ljust(20,b"\x00")
    c1,c2=recalculate_crcs(data); put_be32(data,0x10,c1); put_be32(data,0x14,c2)

def normalize_rom_bytes(data):
    data=bytearray(data); strip_documentation_header(data)
    if len(data)<4: return data
    m=data[0:4]
    if m==V64_MAGIC:
        for i in range(0,len(data)-1,2): data[i],data[i+1]=data[i+1],data[i]
        apply_cart_header_defaults(data); return data
    if m==N64_LE_MAGIC:
        for i in range(0,len(data)-3,4):
            data[i],data[i+3]=data[i+3],data[i]; data[i+1],data[i+2]=data[i+2],data[i+1]
        apply_cart_header_defaults(data); return data
    if m==Z64_MAGIC: apply_cart_header_defaults(data); return data
    return data

def seed_pif_ram(pif, cic):
    pif[:]=b"\x00"*PIF_RAM_SIZE
    for i in range(4): pif[i*4]=0x01
    for i in range(4): pif[0x20+i*4]=pif[0x21+i*4]=pif[0x22+i*4]=pif[0x23+i*4]=0x00
    pif[0x18]=0x00; pif[0x19]=0x04
    cb = {CIC_NUS_6101:(0x00,0x06,0x3F,0x3F),CIC_NUS_6102:(0x00,0x02,0x3F,0x3F),CIC_NUS_6103:(0x00,0x02,0x78,0x3F),CIC_NUS_6105:(0x00,0x02,0x91,0x3F),CIC_NUS_6106:(0x00,0x02,0x85,0x3F)}
    if cic in cb: pif[36],pif[37],pif[38],pif[39]=cb[cic]

def get_rom_region(rom):
    if len(rom)<0x3F: return REGION_NTSC
    return REGION_PAL if rom[0x3E] in (0x44,0x46,0x49,0x50,0x53,0x55,0x58,0x59) else REGION_NTSC

def detect_save_type(rom):
    if len(rom)<0x15: return SAVE_AUTO
    return SAVE_AUTO

class N64Header:
    __slots__=("pi_bsd_dom1_lat","pi_bsd_dom1_pwd","pi_bsd_dom1_pgs","pi_bsd_dom1_rls","clock_rate","boot_address","release","crc1","crc2","title","cart_id")
    def __init__(self,data):
        if len(data)>=0x40:
            self.pi_bsd_dom1_lat=data[0];self.pi_bsd_dom1_pwd=data[1];self.pi_bsd_dom1_pgs=data[2];self.pi_bsd_dom1_rls=data[3]
            self.clock_rate=be32(data,0x04);self.boot_address=be32(data,0x08);self.release=be32(data,0x0C)
            self.crc1=be32(data,0x10);self.crc2=be32(data,0x14)
            self.title=data[0x20:0x34].decode("ascii","ignore").strip("\x00").strip()
            self.cart_id=data[0x3C:0x3E].decode("ascii","ignore")
        else:
            self.clock_rate=0;self.boot_address=0x80000400;self.release=0;self.crc1=self.crc2=0;self.title="UNKNOWN";self.cart_id="??"

@dataclass
class TLBEntry: mask:int=0;vpn2:int=0;g:bool=False;asid:int=0;pfn0:int=0;c0:int=0;d0:bool=False;v0:bool=False;pfn1:int=0;c1:int=0;d1:bool=False;v1:bool=False

_lwl_mask=[0,0xFF,0xFFFF,0xFFFFFF];_lwl_shift=[0,8,16,24]
_lwr_mask=[0xFFFFFF00,0xFFFF0000,0xFF000000,0];_lwr_shift=[24,16,8,0]
_swl_mask=[0,0xFF000000,0xFFFF0000,0xFFFFFF00];_swl_shift=[0,8,16,24]
_swr_mask=[0x00FFFFFF,0x0000FFFF,0x000000FF,0x00000000];_swr_shift=[24,16,8,0]
_ldl_mask=[0,0xFF,0xFFFF,0xFFFFFF,0xFFFFFFFF,0xFFFFFFFFFF,0xFFFFFFFFFFFF,0xFFFFFFFFFFFFFF];_ldl_shift=[0,8,16,24,32,40,48,56]
_ldr_mask=[0xFFFFFFFFFFFFFF00,0xFFFFFFFFFFFF0000,0xFFFFFFFFFF000000,0xFFFFFFFF00000000,0xFFFFFF0000000000,0xFFFF000000000000,0xFF00000000000000,0];_ldr_shift=[56,48,40,32,24,16,8,0]
_sdl_mask=[0,0xFF00000000000000,0xFFFF000000000000,0xFFFFFF0000000000,0xFFFFFFFF00000000,0xFFFFFFFFFF000000,0xFFFFFFFFFFFF0000,0xFFFFFFFFFFFFFF00];_sdl_shift=[0,8,16,24,32,40,48,56]
_sdr_mask=[0x00FFFFFFFFFFFFFF,0x0000FFFFFFFFFFFF,0x000000FFFFFFFFFF,0x00000000FFFFFFFF,0x0000000000FFFFFF,0x000000000000FFFF,0x00000000000000FF,0x0000000000000000];_sdr_shift=[56,48,40,32,24,16,8,0]
_ID_SPECIAL=0x00000;_ID_REGIMM=0x10000;_ID_COP0_RS=0x20000;_ID_COP0_CO=0x30000;_ID_COP1_RS=0x40000;_ID_COP1_BC=0x50000;_ID_FPU=0x60000;_ID_PRIMARY=0x70000
_ID_FPU_S=0;_ID_FPU_D=1;_ID_FPU_W=2;_ID_FPU_L=3;_FPU_FMT_MAP={0x10:_ID_FPU_S,0x11:_ID_FPU_D,0x14:_ID_FPU_W,0x15:_ID_FPU_L}
_DISPATCH:List[Optional[Callable]] = [None] * ((_ID_PRIMARY | 0x3F) + 1)
OP_FORMAT_R="R";OP_FORMAT_I="I";OP_FORMAT_J="J";OP_FORMAT_CP="CP";OP_FORMAT_CP0_CO="CP0_CO";OP_FORMAT_REGIMM="REGIMM";OP_FORMAT_FPU_S="FPU_S";OP_FORMAT_FPU_D="FPU_D";OP_FORMAT_FPU_W="FPU_W";OP_FORMAT_FPU_L="FPU_L";OP_FORMAT_BC="BC";OP_FORMAT_BC1="BC1";OP_FORMAT_FPU_FMT="FPU_FMT"
PRIMARY_OPS={0x00:("SPECIAL",OP_FORMAT_R),0x01:("REGIMM",OP_FORMAT_REGIMM),0x02:("J",OP_FORMAT_J),0x03:("JAL",OP_FORMAT_J),0x04:("BEQ",OP_FORMAT_I),0x05:("BNE",OP_FORMAT_I),0x06:("BLEZ",OP_FORMAT_I),0x07:("BGTZ",OP_FORMAT_I),0x08:("ADDI",OP_FORMAT_I),0x09:("ADDIU",OP_FORMAT_I),0x0A:("SLTI",OP_FORMAT_I),0x0B:("SLTIU",OP_FORMAT_I),0x0C:("ANDI",OP_FORMAT_I),0x0D:("ORI",OP_FORMAT_I),0x0E:("XORI",OP_FORMAT_I),0x0F:("LUI",OP_FORMAT_I),0x10:("COP0",OP_FORMAT_CP),0x11:("COP1",OP_FORMAT_CP),0x12:("COP2",OP_FORMAT_CP),0x13:("COP3",OP_FORMAT_CP),0x14:("BEQL",OP_FORMAT_I),0x15:("BNEL",OP_FORMAT_I),0x16:("BLEZL",OP_FORMAT_I),0x17:("BGTZL",OP_FORMAT_I),0x18:("DADDI",OP_FORMAT_I),0x19:("DADDIU",OP_FORMAT_I),0x1A:("LDL",OP_FORMAT_I),0x1B:("LDR",OP_FORMAT_I),0x1C:("RESERVED_1C",None),0x1D:("RESERVED_1D",None),0x1E:("RESERVED_1E",None),0x1F:("RESERVED_1F",None),0x20:("LB",OP_FORMAT_I),0x21:("LH",OP_FORMAT_I),0x22:("LWL",OP_FORMAT_I),0x23:("LW",OP_FORMAT_I),0x24:("LBU",OP_FORMAT_I),0x25:("LHU",OP_FORMAT_I),0x26:("LWR",OP_FORMAT_I),0x27:("LWU",OP_FORMAT_I),0x28:("SB",OP_FORMAT_I),0x29:("SH",OP_FORMAT_I),0x2A:("SWL",OP_FORMAT_I),0x2B:("SW",OP_FORMAT_I),0x2C:("SDL",OP_FORMAT_I),0x2D:("SDR",OP_FORMAT_I),0x2E:("SWR",OP_FORMAT_I),0x2F:("CACHE",OP_FORMAT_I),0x30:("LL",OP_FORMAT_I),0x31:("LWC1",OP_FORMAT_I),0x32:("LWC2",OP_FORMAT_I),0x33:("LWC3",OP_FORMAT_I),0x34:("LLD",OP_FORMAT_I),0x35:("LDC1",OP_FORMAT_I),0x36:("LDC2",OP_FORMAT_I),0x37:("LD",OP_FORMAT_I),0x38:("SC",OP_FORMAT_I),0x39:("SWC1",OP_FORMAT_I),0x3A:("SWC2",OP_FORMAT_I),0x3B:("SWC3",OP_FORMAT_I),0x3C:("SCD",OP_FORMAT_I),0x3D:("SDC1",OP_FORMAT_I),0x3E:("SDC2",OP_FORMAT_I),0x3F:("SD",OP_FORMAT_I)}
SPECIAL_OPS={0x00:("SLL",OP_FORMAT_R),0x01:("RESERVED_SLL_01",None),0x02:("SRL",OP_FORMAT_R),0x03:("SRA",OP_FORMAT_R),0x04:("SLLV",OP_FORMAT_R),0x05:("RESERVED_SLLV_05",None),0x06:("SRLV",OP_FORMAT_R),0x07:("SRAV",OP_FORMAT_R),0x08:("JR",OP_FORMAT_R),0x09:("JALR",OP_FORMAT_R),0x0A:("MOVZ",OP_FORMAT_R),0x0B:("MOVN",OP_FORMAT_R),0x0C:("SYSCALL",OP_FORMAT_R),0x0D:("BREAK",OP_FORMAT_R),0x0E:("RESERVED_SP_0E",None),0x0F:("SYNC",OP_FORMAT_R),0x10:("MFHI",OP_FORMAT_R),0x11:("MTHI",OP_FORMAT_R),0x12:("MFLO",OP_FORMAT_R),0x13:("MTLO",OP_FORMAT_R),0x14:("DSLLV",OP_FORMAT_R),0x15:("RESERVED_DSLLV_15",None),0x16:("DSRLV",OP_FORMAT_R),0x17:("DSRAV",OP_FORMAT_R),0x18:("MULT",OP_FORMAT_R),0x19:("MULTU",OP_FORMAT_R),0x1A:("DIV",OP_FORMAT_R),0x1B:("DIVU",OP_FORMAT_R),0x1C:("DMULT",OP_FORMAT_R),0x1D:("DMULTU",OP_FORMAT_R),0x1E:("DDIV",OP_FORMAT_R),0x1F:("DDIVU",OP_FORMAT_R),0x20:("ADD",OP_FORMAT_R),0x21:("ADDU",OP_FORMAT_R),0x22:("SUB",OP_FORMAT_R),0x23:("SUBU",OP_FORMAT_R),0x24:("AND",OP_FORMAT_R),0x25:("OR",OP_FORMAT_R),0x26:("XOR",OP_FORMAT_R),0x27:("NOR",OP_FORMAT_R),0x28:("RESERVED_SP_28",None),0x29:("RESERVED_SP_29",None),0x2A:("SLT",OP_FORMAT_R),0x2B:("SLTU",OP_FORMAT_R),0x2C:("DADD",OP_FORMAT_R),0x2D:("DADDU",OP_FORMAT_R),0x2E:("DSUB",OP_FORMAT_R),0x2F:("DSUBU",OP_FORMAT_R),0x30:("TGE",OP_FORMAT_R),0x31:("TGEU",OP_FORMAT_R),0x32:("TLT",OP_FORMAT_R),0x33:("TLTU",OP_FORMAT_R),0x34:("TEQ",OP_FORMAT_R),0x35:("RESERVED_SP_35",None),0x36:("TNE",OP_FORMAT_R),0x37:("RESERVED_SP_37",None),0x38:("DSLL",OP_FORMAT_R),0x39:("RESERVED_DSLL_39",None),0x3A:("DSRL",OP_FORMAT_R),0x3B:("DSRA",OP_FORMAT_R),0x3C:("DSLL32",OP_FORMAT_R),0x3D:("RESERVED_DSLL32_3D",None),0x3E:("DSRL32",OP_FORMAT_R),0x3F:("DSRA32",OP_FORMAT_R)}
REGIMM_OPS={0x00:("BLTZ",OP_FORMAT_I),0x01:("BGEZ",OP_FORMAT_I),0x02:("BLTZL",OP_FORMAT_I),0x03:("BGEZL",OP_FORMAT_I),0x04:("RESERVED_RI_04",None),0x05:("RESERVED_RI_05",None),0x06:("RESERVED_RI_06",None),0x07:("RESERVED_RI_07",None),0x08:("TGEI",OP_FORMAT_I),0x09:("TGEIU",OP_FORMAT_I),0x0A:("TLTI",OP_FORMAT_I),0x0B:("TLTIU",OP_FORMAT_I),0x0C:("TEQI",OP_FORMAT_I),0x0D:("RESERVED_RI_0D",None),0x0E:("TNEI",OP_FORMAT_I),0x0F:("RESERVED_RI_0F",None),0x10:("BLTZAL",OP_FORMAT_I),0x11:("BGEZAL",OP_FORMAT_I),0x12:("BLTZALL",OP_FORMAT_I),0x13:("BGEZALL",OP_FORMAT_I)}
COP0_RS={0x00:("MFC0",OP_FORMAT_CP),0x01:("DMFC0",OP_FORMAT_CP),0x02:("CFC0",OP_FORMAT_CP),0x03:("RESERVED_C0_RS_03",None),0x04:("MTC0",OP_FORMAT_CP),0x05:("DMTC0",OP_FORMAT_CP),0x06:("CTC0",OP_FORMAT_CP),0x07:("RESERVED_C0_RS_07",None),0x08:("BC0",OP_FORMAT_BC),0x09:("RESERVED_C0_RS_09",None),0x0A:("RESERVED_C0_RS_0A",None),0x0B:("RESERVED_C0_RS_0B",None),0x0C:("RESERVED_C0_RS_0C",None),0x0D:("RESERVED_C0_RS_0D",None),0x0E:("RESERVED_C0_RS_0E",None),0x0F:("RESERVED_C0_RS_0F",None),0x10:("COP0_CO",OP_FORMAT_CP0_CO)}
COP0_CO={0x00:("RESERVED_C0_CO_00",None),0x01:("TLBR",OP_FORMAT_CP0_CO),0x02:("TLBWI",OP_FORMAT_CP0_CO),0x03:("RESERVED_C0_CO_03",None),0x04:("RESERVED_C0_CO_04",None),0x05:("RESERVED_C0_CO_05",None),0x06:("TLBWR",OP_FORMAT_CP0_CO),0x07:("RESERVED_C0_CO_07",None),0x08:("TLBP",OP_FORMAT_CP0_CO),0x18:("ERET",OP_FORMAT_CP0_CO)}
COP1_RS={0x00:("MFC1",OP_FORMAT_CP),0x01:("DMFC1",OP_FORMAT_CP),0x02:("CFC1",OP_FORMAT_CP),0x03:("RESERVED_C1_RS_03",None),0x04:("MTC1",OP_FORMAT_CP),0x05:("DMTC1",OP_FORMAT_CP),0x06:("CTC1",OP_FORMAT_CP),0x07:("RESERVED_C1_RS_07",None),0x08:("BC1",OP_FORMAT_BC1),0x10:("S",OP_FORMAT_FPU_S),0x11:("D",OP_FORMAT_FPU_D),0x14:("W",OP_FORMAT_FPU_W),0x15:("L",OP_FORMAT_FPU_L)}
COP1_FUNCT={0x00:("ADD",OP_FORMAT_FPU_FMT),0x01:("SUB",OP_FORMAT_FPU_FMT),0x02:("MUL",OP_FORMAT_FPU_FMT),0x03:("DIV",OP_FORMAT_FPU_FMT),0x04:("SQRT",OP_FORMAT_FPU_FMT),0x05:("ABS",OP_FORMAT_FPU_FMT),0x06:("MOV",OP_FORMAT_FPU_FMT),0x07:("NEG",OP_FORMAT_FPU_FMT),0x08:("ROUND.L",OP_FORMAT_FPU_FMT),0x09:("TRUNC.L",OP_FORMAT_FPU_FMT),0x0A:("CEIL.L",OP_FORMAT_FPU_FMT),0x0B:("FLOOR.L",OP_FORMAT_FPU_FMT),0x0C:("ROUND.W",OP_FORMAT_FPU_FMT),0x0D:("TRUNC.W",OP_FORMAT_FPU_FMT),0x0E:("CEIL.W",OP_FORMAT_FPU_FMT),0x0F:("FLOOR.W",OP_FORMAT_FPU_FMT),0x20:("CVT.S",OP_FORMAT_FPU_FMT),0x21:("CVT.D",OP_FORMAT_FPU_FMT),0x24:("CVT.W",OP_FORMAT_FPU_FMT),0x25:("CVT.L",OP_FORMAT_FPU_FMT),0x30:("C.F",OP_FORMAT_FPU_FMT),0x31:("C.UN",OP_FORMAT_FPU_FMT),0x32:("C.EQ",OP_FORMAT_FPU_FMT),0x33:("C.UEQ",OP_FORMAT_FPU_FMT),0x34:("C.OLT",OP_FORMAT_FPU_FMT),0x35:("C.ULT",OP_FORMAT_FPU_FMT),0x36:("C.OLE",OP_FORMAT_FPU_FMT),0x37:("C.ULE",OP_FORMAT_FPU_FMT),0x38:("C.SF",OP_FORMAT_FPU_FMT),0x39:("C.NGLE",OP_FORMAT_FPU_FMT),0x3A:("C.SEQ",OP_FORMAT_FPU_FMT),0x3B:("C.NGL",OP_FORMAT_FPU_FMT),0x3C:("C.LT",OP_FORMAT_FPU_FMT),0x3D:("C.NGE",OP_FORMAT_FPU_FMT),0x3E:("C.LE",OP_FORMAT_FPU_FMT),0x3F:("C.NGT",OP_FORMAT_FPU_FMT)}

@dataclass
class CheatCode: name:str="";code:str="";enabled:bool=True
class CheatEngine:
    def __init__(self): self.codes:List[CheatCode]=[]; self.active:List[CheatCode]=[]
    def add(self,name,code): cc=CheatCode(name=name,code=code,enabled=True); self.codes.append(cc); self.active.append(cc)
    def toggle(self,idx):
        if 0<=idx<len(self.codes): self.codes[idx].enabled=not self.codes[idx].enabled; self.active=[c for c in self.codes if c.enabled]
    def apply(self,bus,rdram):
        for cc in self.active:
            if not cc.code.strip(): continue
            try:
                parts=cc.code.strip().split()
                if len(parts)>=2 and len(parts[0])==8 and len(parts[1])==8:
                    addr=int(parts[0],16);val=int(parts[1],16);ct=(addr>>28)&0xF;aa=(addr&0x0FFFFFFF)&0x00FFFFFF
                    if ct==0 and aa<RDRAM_SIZE-3: put_be32(rdram,aa,val)
                    elif ct==1 and aa<RDRAM_SIZE-1: struct.pack_into(">H",rdram,aa,val&MASK_16)
            except: pass

class SaveManager:
    def __init__(self):
        self.save_type=SAVE_AUTO; self.eeprom=bytearray(EEPROM_16K_SIZE); self.sram=bytearray(SRAM_SIZE)
        self.flashram=bytearray(FLASHRAM_SIZE); self.flashram_mode=0; self.flashram_addr=0; self.dirty=False
    def reset(self):
        self.eeprom=bytearray(EEPROM_16K_SIZE); self.sram=bytearray(SRAM_SIZE); self.flashram=bytearray(FLASHRAM_SIZE)
        self.flashram_mode=0; self.flashram_addr=0
    def get_save_size(self): return {SAVE_EEPROM_4K:EEPROM_4K_SIZE,SAVE_EEPROM_16K:EEPROM_16K_SIZE,SAVE_SRAM:SRAM_SIZE,SAVE_FLASHRAM:FLASHRAM_SIZE}.get(self.save_type,0)
    def pi_read(self,ca,ln,rdram,da):
        if self.save_type==SAVE_SRAM and 0<=ca<SRAM_SIZE:
            ln=min(ln,SRAM_SIZE-ca,RDRAM_SIZE-da)
            if ln>0: rdram[da:da+ln]=self.sram[ca:ca+ln]
        elif self.save_type==SAVE_FLASHRAM and 0<=ca<FLASHRAM_SIZE:
            if self.flashram_mode==1:
                ln=min(ln,FLASHRAM_SIZE-ca,RDRAM_SIZE-da)
                if ln>0: rdram[da:da+ln]=self.flashram[ca:ca+ln]
    def pi_write(self,ca,ln,rdram,da):
        if self.save_type==SAVE_SRAM and 0<=ca<SRAM_SIZE:
            ln=min(ln,SRAM_SIZE-ca,RDRAM_SIZE-da)
            if ln>0: self.sram[ca:ca+ln]=rdram[da:da+ln]; self.dirty=True
        elif self.save_type==SAVE_FLASHRAM and 0<=ca<FLASHRAM_SIZE: self._flashram_execute(ca,ln,rdram,da)
    def _flashram_execute(self,ca,ln,rdram,da):
        if self.flashram_mode==0:
            if ln>=4:
                cmd=be32(rdram,da)
                if cmd==0xFFFFFFFF: self.flashram_mode=3
                elif (cmd&0xFF000000)==0xA5000000:
                    self.flashram_addr=(cmd&0x00FFFF)<<1
                    if cmd&0x00008000: self.flashram_mode=2
                    else: self.flashram_mode=1
        elif self.flashram_mode==1: self.pi_read(ca,ln,rdram,da)
        elif self.flashram_mode==2:
            ln=min(ln,FLASHRAM_SIZE-self.flashram_addr,RDRAM_SIZE-da)
            if ln>0: self.flashram[self.flashram_addr:self.flashram_addr+ln]=rdram[da:da+ln]; self.dirty=True
            self.flashram_mode=0
        elif self.flashram_mode==3:
            if ca==0: self.flashram=bytearray(FLASHRAM_SIZE); self.dirty=True
            self.flashram_mode=0

def rdram_rgb5551_to_ppm(rdram,origin,width,height):
    origin&=0xFFFFFF; width=max(1,min(width,320)); height=max(1,min(height,240)); stride=width*2
    need=origin+stride*height
    if origin<0 or need>len(rdram): return None
    hdr=f"P6\n{width} {height}\n255\n".encode("ascii"); out=bytearray(width*height*3); mv=memoryview(rdram); o=0
    for y in range(height):
        row=origin+y*stride
        for x in range(0,stride,2):
            px=(mv[row+x]<<8)|mv[row+x+1]; out[o]=((px>>11)&0x1F)<<3; out[o+1]=((px>>6)&0x1F)<<3; out[o+2]=((px>>1)&0x1F)<<3; o+=3
    return hdr+bytes(out)

def normalize_commercial_entry(addr):
    addr=u32(addr)
    if addr==0 or addr==MASK_32: return 0x80000400
    hi=addr>>24
    if hi in (0x80,0xA0,0xB0):
        if hi==0xB0: return 0x80000000|(addr&0x1FFFFFFF)
        return addr
    if addr<RDRAM_SIZE: return 0x80000000|addr
    if hi==0 and addr<0x04000000: return 0x80000000|addr
    return addr

def default_rom_directory():
    try: os.makedirs(_DEFAULT_ROM_DIR,exist_ok=True); return _DEFAULT_ROM_DIR
    except OSError: return _SCRIPT_DIR

R4300_CP0_REG_NAMES={0:"Index",1:"Random",2:"EntryLo0",3:"EntryLo1",4:"Context",5:"PageMask",6:"Wired",7:"Reserved_7",8:"BadVAddr",9:"Count",10:"EntryHi",11:"Compare",12:"Status",13:"Cause",14:"EPC",15:"PRId",16:"Config",17:"LLAddr",30:"ErrorEPC"}

class N64Opcode:
    __slots__=("word","op","rs","rt","rd","sa","funct","imm","simm","target","instr_id")
    def __init__(self,word):
        self.word=word&MASK_32; self.op=(self.word>>26)&0x3F; self.rs=(self.word>>21)&0x1F; self.rt=(self.word>>16)&0x1F
        self.rd=(self.word>>11)&0x1F; self.sa=(self.word>>6)&0x1F; self.funct=self.word&0x3F; self.imm=self.word&MASK_16; self.simm=sign16(self.imm); self.target=self.word&0x03FFFFFF
        if self.op==0: self.instr_id=_ID_SPECIAL|self.funct
        elif self.op==1: self.instr_id=_ID_REGIMM|self.rt
        elif self.op==0x10:
            if self.rs==0x10: self.instr_id=_ID_COP0_CO|self.funct
            else: self.instr_id=_ID_COP0_RS|self.rs
        elif self.op==0x11:
            if self.rs in _FPU_FMT_MAP: self.instr_id=_ID_FPU|(_FPU_FMT_MAP[self.rs]<<6)|self.funct
            elif self.rs==0x08: self.instr_id=_ID_COP1_BC|self.rt
            else: self.instr_id=_ID_COP1_RS|self.rs
        else: self.instr_id=_ID_PRIMARY|self.op
    def target_addr(self,pc): return u32(((pc+4)&0xF0000000)|(self.target<<2))
    def branch_addr(self,pc): return u32(pc+4+(self.simm<<2))


# ── DeviceBus with full PJ64-Legacy register MMIO ──
class DeviceBus:
    def __init__(self, core):
        self.core = core
        self.regs = {}
        self.hw_interrupts = 0
        self.mi_intr_mask = 0
        self.mi_mode = 0
        self.mi_version = 0x02020102
        self.sp_status = SP_STATUS_HALT
        self.dpc_status = 0
        self.dps_regs = {}
        self.vi_field_serration = 0
        self.half_line = 0
        self.sp_dma_busy = False
        self.reset()

    def reset(self):
        self.regs.clear()
        self.hw_interrupts = 0
        self.mi_intr_mask = 0
        self.mi_mode = 0
        self.sp_status = SP_STATUS_HALT
        self.dpc_status = 0
        self.dps_regs.clear()
        self.vi_field_serration = 0
        self.half_line = 0
        self.sp_dma_busy = False
        self.regs[VI_ORIGIN] = 0
        self.regs[VI_WIDTH] = 320
        self.regs[VI_V_CURRENT] = 0x3FF
        self.regs[VI_INTR] = 0x3FF
        self.core._vi_origin_set = False

    def v_to_p(self, addr):
        addr &= MASK_32
        seg = addr >> 29
        if seg in (0b100, 0b101):
            return addr & 0x1FFFFFFF
        tlb = self.core.cpu.tlb
        asid = self.core.cpu.cp0[CP0_ENTRYHI] & 0xFF
        vpn2 = (addr >> 13) & 0x7FFFF
        for entry in tlb:
            if entry.mask:
                extra = ((entry.mask >> 12) & 1) | ((entry.mask >> 13) & 1)
                if extra:
                    ms = 13 - extra
                    vpn2_m = (addr >> ms) & (0x7FFFF >> extra)
                    ev = entry.vpn2 >> extra
                    if ev == vpn2_m and (entry.g or entry.asid == asid):
                        eo = (addr >> (12 + extra)) & 1
                        offset_mask = (1 << (12 + extra)) - 1
                        if eo == 0 and entry.v0:
                            return ((entry.pfn0 >> extra) << (12 + extra)) | (addr & offset_mask)
                        if eo == 1 and entry.v1:
                            return ((entry.pfn1 >> extra) << (12 + extra)) | (addr & offset_mask)
            elif entry.vpn2 == vpn2 and (entry.g or entry.asid == asid):
                eo = (addr >> 12) & 1
                if eo == 0 and entry.v0:
                    return (entry.pfn0 << 12) | (addr & 0xFFF)
                if eo == 1 and entry.v1:
                    return (entry.pfn1 << 12) | (addr & 0xFFF)
        return addr & 0x1FFFFFFF

    def read_u8(self, addr):
        p = self.v_to_p(addr)
        if 0 <= p < RDRAM_SIZE: return self.core.rdram[p]
        if 0x04000000 <= p < 0x04002000:
            off = p - 0x04000000
            return (self.core.rsp_dmem if off < 0x1000 else self.core.rsp_imem)[off & 0xFFF]
        if 0x10000000 <= p < 0x10000000 + len(self.core.rom): return self.core.rom[p - 0x10000000]
        if 0x1FC007C0 <= p < 0x1FC007C0 + PIF_RAM_SIZE: return self.core.pif_ram[p - 0x1FC007C0]
        return 0

    def read_u16(self, addr):
        p = self.v_to_p(addr)
        rdram = self.core.rdram
        if 0 <= p < RDRAM_SIZE - 1: return (rdram[p] << 8) | rdram[p + 1]
        if 0x04000000 <= p < 0x04002000 - 1:
            off = p - 0x04000000
            buf = self.core.rsp_dmem if off < 0x1000 else self.core.rsp_imem
            return (buf[off & 0xFFF] << 8) | buf[(off & 0xFFF) + 1]
        return 0

    def read_u32(self, addr):
        p = self.v_to_p(addr)
        rdram = self.core.rdram
        if p <= RDRAM_SIZE - 4 >= 0:
            return (rdram[p] << 24) | (rdram[p + 1] << 16) | (rdram[p + 2] << 8) | rdram[p + 3]
        if 0x04000000 <= p < 0x04002000:
            off = p & 0xFFF
            buf = self.core.rsp_dmem if p < 0x04001000 else self.core.rsp_imem
            return (buf[off] << 24) | (buf[off + 1] << 16) | (buf[off + 2] << 8) | buf[off + 3]
        if 0x04040000 <= p <= 0x048FFFFF: return self._read_mmio(p)
        roff = p - 0x10000000
        rom = self.core.rom
        if 0 <= roff <= len(rom) - 4:
            return (rom[roff] << 24) | (rom[roff + 1] << 16) | (rom[roff + 2] << 8) | rom[roff + 3]
        return 0

    def read_u64(self, addr): return (self.read_u32(addr) << 32) | self.read_u32(addr + 4)

    def _read_mmio(self, p):
        al = p & ~3
        if al == SP_STATUS: return self.sp_status
        if al in (SP_DMA_FULL, SP_DMA_BUSY): return 0
        if al == SP_PC: return self.core.rsp_pc
        if al == DPC_STATUS: return self.dpc_status
        if al == MI_MODE: return self.mi_mode
        if al == MI_VERSION: return self.mi_version
        if al == MI_INTR: return self.hw_interrupts
        if al == MI_INTR_MASK: return self.mi_intr_mask
        if al == VI_V_CURRENT: return self.half_line
        if VI_STATUS <= al <= VI_Y_SCALE: return self.regs.get(al, 0)
        if AI_DRAM_ADDR <= al <= AI_BITRATE: return self.regs.get(al, 0)
        if al == AI_STATUS: return self.regs.get(al, 0)
        if PI_DRAM_ADDR <= al <= PI_DOM2_RLS: return self.regs.get(al, 0)
        if al == SI_STATUS: return 0
        if SI_DRAM_ADDR <= al <= SI_PIF_ADDR_WR: return self.regs.get(al, 0)
        if RI_MODE <= al <= RI_WERROR: return self.regs.get(al, 0)
        if al in (DPC_START, DPC_END, DPC_CURRENT, DPC_CLOCK, DPC_BUFBUSY, DPC_PIPEBUSY, DPC_TMEM): return self.regs.get(al, 0)
        if al in (DPS_TBIST, DPS_TEST_MODE, DPS_BUFTEST, DPS_DETAIL): return self.dps_regs.get(al, 0)
        return self.regs.get(al, 0)

    def write_u8(self, addr, val):
        p = self.v_to_p(addr)
        val &= MASK_8
        if 0 <= p < RDRAM_SIZE: self.core.rdram[p] = val; return
        if 0x04000000 <= p < 0x04002000:
            off = p & 0xFFF
            buf = self.core.rsp_dmem if p < 0x04001000 else self.core.rsp_imem
            buf[off] = val; return
        if 0x1FC007C0 <= p < 0x1FC007C0 + PIF_RAM_SIZE: self.core.pif_ram[p - 0x1FC007C0] = val

    def write_u16(self, addr, val):
        p = self.v_to_p(addr)
        if 0 <= p < RDRAM_SIZE - 1:
            rdram = self.core.rdram; val &= MASK_16
            rdram[p] = (val >> 8) & MASK_8; rdram[p + 1] = val & MASK_8; return
        if 0x04000000 <= p < 0x04002000 - 1:
            off = p & 0xFFF; val &= MASK_16
            buf = self.core.rsp_dmem if p < 0x04001000 else self.core.rsp_imem
            buf[off] = (val >> 8) & MASK_8; buf[off + 1] = val & MASK_8

    def write_u32(self, addr, val):
        p = self.v_to_p(addr)
        rdram = self.core.rdram
        if p <= RDRAM_SIZE - 4 >= 0:
            val &= MASK_32
            rdram[p] = (val >> 24) & MASK_8; rdram[p + 1] = (val >> 16) & MASK_8
            rdram[p + 2] = (val >> 8) & MASK_8; rdram[p + 3] = val & MASK_8; return
        if 0x04000000 <= p < 0x04002000:
            off = p & 0xFFF; val &= MASK_32
            buf = self.core.rsp_dmem if p < 0x04001000 else self.core.rsp_imem
            buf[off] = (val >> 24) & MASK_8; buf[off + 1] = (val >> 16) & MASK_8
            buf[off + 2] = (val >> 8) & MASK_8; buf[off + 3] = val & MASK_8; return
        if 0x04040000 <= p <= 0x048FFFFF: self._write_mmio(p, val)

    def write_u64(self, addr, val):
        val &= MASK_64; self.write_u32(addr, (val >> 32) & MASK_32); self.write_u32(addr + 4, val & MASK_32)

    def _change_sp_status(self, mv):
        if mv & SP_CLR_HALT: self.sp_status &= ~SP_STATUS_HALT
        if mv & SP_SET_HALT: self.sp_status |= SP_STATUS_HALT
        if mv & SP_CLR_BROKE: self.sp_status &= ~SP_STATUS_BROKE
        if mv & SP_CLR_INTR: self.hw_interrupts &= ~MI_INTR_SP
        if mv & SP_CLR_SSTEP: self.sp_status &= ~SP_STATUS_SSTEP
        if mv & SP_SET_SSTEP: self.sp_status |= SP_STATUS_SSTEP
        if mv & SP_CLR_INTR_BREAK: self.sp_status &= ~SP_STATUS_INTR_BREAK
        if mv & SP_SET_INTR_BREAK: self.sp_status |= SP_STATUS_INTR_BREAK
        for i in range(8):
            clr = [SP_CLR_SIG0,SP_CLR_SIG1,SP_CLR_SIG2,SP_CLR_SIG3,SP_CLR_SIG4,SP_CLR_SIG5,SP_CLR_SIG6,SP_CLR_SIG7][i]
            set_ = [SP_SET_SIG0,SP_SET_SIG1,SP_SET_SIG2,SP_SET_SIG3,SP_SET_SIG4,SP_SET_SIG5,SP_SET_SIG6,SP_SET_SIG7][i]
            if mv & clr: self.sp_status &= ~(0x80 << i)
            if mv & set_: self.sp_status |= (0x80 << i)
        if (mv & SP_SET_SIG0) and self.core.audio_signal: self.hw_interrupts |= MI_INTR_SP
        if not (self.sp_status & SP_STATUS_HALT): self.core.process_rsp()

    def _change_dpc_status(self, mv):
        if mv & DPC_CLR_XBUS_DMEM_DMA: self.dpc_status &= ~DPC_STATUS_XBUS_DMEM_DMA
        if mv & DPC_SET_XBUS_DMEM_DMA: self.dpc_status |= DPC_STATUS_XBUS_DMEM_DMA
        if mv & DPC_CLR_FREEZE: self.dpc_status &= ~DPC_STATUS_FREEZE
        if mv & DPC_SET_FREEZE: self.dpc_status |= DPC_STATUS_FREEZE
        if mv & DPC_CLR_FLUSH: self.dpc_status &= ~DPC_STATUS_FLUSH
        if mv & DPC_SET_FLUSH: self.dpc_status |= DPC_STATUS_FLUSH
        if (mv & DPC_CLR_FREEZE) and not (self.sp_status & SP_STATUS_HALT) and not (self.sp_status & SP_STATUS_BROKE):
            self.core.process_rsp()

    def _change_mi_mode(self, mv):
        if mv & MI_CLR_INIT: self.mi_mode &= ~MI_MODE_INIT
        if mv & MI_SET_INIT: self.mi_mode |= MI_MODE_INIT
        if mv & MI_CLR_EBUS: self.mi_mode &= ~MI_MODE_EBUS
        if mv & MI_SET_EBUS: self.mi_mode |= MI_MODE_EBUS
        if mv & MI_CLR_DP_INTR: self.hw_interrupts &= ~MI_INTR_DP
        if mv & MI_CLR_RDRAM: self.mi_mode &= ~MI_MODE_RDRAM
        if mv & MI_SET_RDRAM: self.mi_mode |= MI_MODE_RDRAM

    def _change_mi_intr_mask(self, mv):
        if mv & MI_INTR_MASK_CLR_SP: self.mi_intr_mask &= ~MI_INTR_SP
        if mv & MI_INTR_MASK_SET_SP: self.mi_intr_mask |= MI_INTR_SP
        if mv & MI_INTR_MASK_CLR_SI: self.mi_intr_mask &= ~MI_INTR_SI
        if mv & MI_INTR_MASK_SET_SI: self.mi_intr_mask |= MI_INTR_SI
        if mv & MI_INTR_MASK_CLR_AI: self.mi_intr_mask &= ~MI_INTR_AI
        if mv & MI_INTR_MASK_SET_AI: self.mi_intr_mask |= MI_INTR_AI
        if mv & MI_INTR_MASK_CLR_VI: self.mi_intr_mask &= ~MI_INTR_VI
        if mv & MI_INTR_MASK_SET_VI: self.mi_intr_mask |= MI_INTR_VI
        if mv & MI_INTR_MASK_CLR_PI: self.mi_intr_mask &= ~MI_INTR_PI
        if mv & MI_INTR_MASK_SET_PI: self.mi_intr_mask |= MI_INTR_PI
        if mv & MI_INTR_MASK_CLR_DP: self.mi_intr_mask &= ~MI_INTR_DP
        if mv & MI_INTR_MASK_SET_DP: self.mi_intr_mask |= MI_INTR_DP

    def _write_mmio(self, p, val):
        al = p & ~3
        if al in (SP_MEM_ADDR, SP_DRAM_ADDR, SP_RD_LEN, SP_WR_LEN, SP_SEMAPHORE, SP_PC, SP_IBIST):
            self.regs[al] = val
            if al == SP_RD_LEN: self.core.trigger_sp_dma(to_rsp=True)
            elif al == SP_WR_LEN: self.core.trigger_sp_dma(to_rsp=False)
            elif al == SP_PC: self.core.rsp_pc = val
        elif al == SP_STATUS: self._change_sp_status(val)
        elif al == DPC_STATUS: self._change_dpc_status(val)
        elif al in (DPC_START, DPC_END, DPC_CURRENT, DPC_CLOCK, DPC_BUFBUSY, DPC_PIPEBUSY, DPC_TMEM):
            if al == DPC_END: self.core.process_rdp(); self.regs[DPC_CURRENT] = val
            self.regs[al] = val
        elif al in (DPS_TBIST, DPS_TEST_MODE, DPS_BUFTEST, DPS_DETAIL): self.dps_regs[al] = val
        elif al == MI_MODE: self._change_mi_mode(val)
        elif al == MI_INTR: self.hw_interrupts &= ~val
        elif al == MI_INTR_MASK: self._change_mi_intr_mask(val)
        elif al == VI_ORIGIN:
            self.regs[VI_ORIGIN] = val
            if (val & 0xFFFFFF) != 0: self.core._vi_origin_set = True
        elif al in (VI_STATUS, VI_WIDTH, VI_BURST, VI_V_SYNC, VI_H_SYNC, VI_LEAP, VI_H_START, VI_V_START, VI_V_BURST, VI_X_SCALE, VI_Y_SCALE): self.regs[al] = val
        elif al == VI_INTR: self.regs[VI_INTR] = val & 0x3FF; self.half_line = 0
        elif al == AI_DRAM_ADDR: self.regs[AI_DRAM_ADDR] = val & 0x00FFFFFF
        elif al == AI_LEN: self.regs[AI_LEN] = val; self.core.process_audio()
        elif al == AI_CONTROL: self.regs[AI_CONTROL] = val; self.regs[AI_STATUS] = self.regs.get(AI_STATUS,0) & ~AI_STATUS_DMA_BUSY
        elif al in (AI_DACRATE, AI_BITRATE): self.regs[al] = val
        elif al == PI_DRAM_ADDR: self.regs[PI_DRAM_ADDR] = val & 0x00FFFFFF
        elif al == PI_CART_ADDR: self.regs[PI_CART_ADDR] = val
        elif al == PI_RD_LEN: self.regs[PI_RD_LEN] = val; self.core.trigger_pi_dma()
        elif al == PI_WR_LEN: self.regs[PI_WR_LEN] = val; self.core.trigger_pi_dma()
        elif al == PI_STATUS:
            if val & 1: regsval = self.regs.get(PI_STATUS,0) & ~1
            if val & 2: self.hw_interrupts &= ~MI_INTR_PI
        elif PI_DOM1_LAT <= al <= PI_DOM2_RLS: self.regs[al] = val
        elif al == SI_DRAM_ADDR: self.regs[SI_DRAM_ADDR] = val
        elif al == SI_PIF_ADDR_RD: self.core.trigger_si_dma(read_pif=True)
        elif al == SI_PIF_ADDR_WR: self.core.trigger_si_dma(read_pif=False)
        elif RI_MODE <= al <= RI_WERROR: self.regs[al] = val
        else: self.regs[al] = val

# ── CPUCore (R4300i interpreter) ──
class CPUCore:
    def __init__(self, core):
        self.core = core
        self.gpr = [0] * 32
        self.fpr = [0] * 32
        self.cp0 = [0] * 32
        self.fcr0 = 0x00000511
        self.fcr31 = 0
        self.hi = 0
        self.lo = 0
        self.pc = 0
        self.next_pc = 4
        self.llbit = False
        self.lladdr = 0
        self.tlb = [TLBEntry() for _ in range(32)]
        self.reset()

    def reset(self):
        self.gpr = [0] * 32; self.fpr = [0] * 32; self.cp0 = [0] * 32
        self.fcr0 = 0x00000511; self.fcr31 = 0; self.hi = 0; self.lo = 0; self.pc = 0; self.next_pc = 4
        self.cp0[CP0_PRID] = 0x00000B00; self.cp0[CP0_STATUS] = 0x34000000; self.cp0[CP0_CONFIG] = 0x7006E463
        self.cp0[CP0_WIRED] = 0; self.cp0[CP0_CONTEXT] = 0x007FFFF0; self.cp0[CP0_EPC] = 0xFFFFFFFF
        self.cp0[CP0_BADVADDR] = 0xFFFFFFFF; self.cp0[CP0_ERROREPC] = 0xFFFFFFFF; self.cp0[CP0_CAUSE] = 0xB000005C
        self.llbit = False; self.lladdr = 0; self.tlb = [TLBEntry() for _ in range(32)]

    def step(self):
        bus = self.core.bus
        cp0 = self.cp0
        mi_hw = bus.hw_interrupts
        status = cp0[CP0_STATUS]
        if mi_hw & 0x3F and (status & STATUS_IE) and not (status & STATUS_EXL):
            im = (status >> 8) & 0x3F
            ip = 0
            if mi_hw & (MI_INTR_SP | MI_INTR_DP): ip |= 0x04
            if mi_hw & MI_INTR_SI: ip |= 0x08
            if mi_hw & MI_INTR_AI: ip |= 0x10
            if mi_hw & (MI_INTR_VI | MI_INTR_PI): ip |= 0x20
            if ip & im:
                cp0[CP0_CAUSE] = (cp0[CP0_CAUSE] & ~(0x3F << 10)) | (ip << 10)
                cp0[CP0_STATUS] |= STATUS_EXL; cp0[CP0_EPC] = self.pc
                use_bev = bool(cp0[CP0_STATUS] & STATUS_BEV)
                self.pc = 0x80000180 if not use_bev else 0xBFC00380
                self.next_pc = self.pc + 4
        word = bus.read_u32(self.pc)
        i = N64Opcode(word)
        self.execute(i)
        self.gpr[0] = 0
        cp0[CP0_COUNT] = u32(cp0[CP0_COUNT] + 1)
        if cp0[CP0_COUNT] == cp0[CP0_COMPARE]:
            cp0[CP0_CAUSE] |= 1 << 15
            bus.hw_interrupts |= MI_INTR_SP

    def _branch(self, target): self.next_pc = u32(target)
    def _skip_likely(self): self.pc = u32(self.pc + 4); self.next_pc = u32(self.pc + 4)

    def _write_tlb_entry(self, index):
        idx = index % 32; hi = self.cp0[CP0_ENTRYHI]; lo0 = self.cp0[CP0_ENTRYLO0]; lo1 = self.cp0[CP0_ENTRYLO1]
        pm = self.cp0[CP0_PAGEMASK]
        self.tlb[idx].mask = pm; self.tlb[idx].vpn2 = (hi >> 13) & 0x7FFFF; self.tlb[idx].asid = hi & 0xFF
        self.tlb[idx].g = bool((lo0 & 1) and (lo1 & 1))
        self.tlb[idx].pfn0 = (lo0 >> 6) & 0xFFFFF; self.tlb[idx].c0 = (lo0 >> 3) & 7
        self.tlb[idx].d0 = bool((lo0 >> 2) & 1); self.tlb[idx].v0 = bool((lo0 >> 1) & 1)
        self.tlb[idx].pfn1 = (lo1 >> 6) & 0xFFFFF; self.tlb[idx].c1 = (lo1 >> 3) & 7
        self.tlb[idx].d1 = bool((lo1 >> 2) & 1); self.tlb[idx].v1 = bool((lo1 >> 1) & 1)

    def _raise_exception(self, exc_code, old_pc):
        self.cp0[CP0_CAUSE] = (self.cp0[CP0_CAUSE] & ~0x80000000) | (exc_code << 2)
        self.cp0[CP0_EPC] = old_pc; self.cp0[CP0_STATUS] |= STATUS_EXL
        use_bev = bool(self.cp0[CP0_STATUS] & STATUS_BEV)
        self.pc = 0x80000180 if not use_bev else 0xBFC00380; self.next_pc = self.pc + 4

    def _test_cop1_usable(self): return bool(self.cp0[CP0_STATUS] & STATUS_CU1)
    def _clear_fp_cause(self): self.fcr31 &= ~0x3F000
    def _set_fp_cause(self, cause): self.fcr31 &= ~0x3F000; self.fcr31 |= (cause & 0x3F) << 12
    def _set_fp_flags(self, cause): self.fcr31 |= (cause & 0x3F) << 2

    def execute(self, o):
        old_pc = self.pc; self.pc = self.next_pc; self.next_pc = u32(self.next_pc + 4)
        g = self.gpr
        h = _DISPATCH[o.instr_id]
        if h is not None: h(self, o, old_pc, g)
        elif o.op in (0x10, 0x11, 0x12, 0x13): self._raise_exception(11, old_pc)
        else: self._raise_exception(10, old_pc)

# ── Instruction handlers ──
def _h_NOP(cpu, o, old_pc, g): pass
def _h_LUI(cpu, o, old_pc, g): g[o.rt] = sx32_to_64(o.imm << 16)
def _h_ORI(cpu, o, old_pc, g): g[o.rt] = u64(g[o.rs] | o.imm)
def _h_ANDI(cpu, o, old_pc, g): g[o.rt] = u64(g[o.rs] & o.imm)
def _h_XORI(cpu, o, old_pc, g): g[o.rt] = u64(g[o.rs] ^ o.imm)
def _h_ADDI(cpu, o, old_pc, g): g[o.rt] = sx32_to_64(u32(g[o.rs] + o.simm))
def _h_ADDIU(cpu, o, old_pc, g): g[o.rt] = sx32_to_64(u32(g[o.rs] + o.simm))
def _h_DADDI(cpu, o, old_pc, g): g[o.rt] = u64(g[o.rs] + o.simm)
def _h_DADDIU(cpu, o, old_pc, g): g[o.rt] = u64(g[o.rs] + o.simm)
def _h_SLTI(cpu, o, old_pc, g): g[o.rt] = 1 if sign64(g[o.rs]) < o.simm else 0
def _h_SLTIU(cpu, o, old_pc, g): g[o.rt] = 1 if g[o.rs] < u64(o.simm) else 0
def _h_LB(cpu, o, old_pc, g): g[o.rt] = sx8_to_64(cpu.core.bus.read_u8(g[o.rs] + o.simm))
def _h_LBU(cpu, o, old_pc, g): g[o.rt] = cpu.core.bus.read_u8(g[o.rs] + o.simm)
def _h_LH(cpu, o, old_pc, g): g[o.rt] = sx16_to_64(cpu.core.bus.read_u16(g[o.rs] + o.simm))
def _h_LHU(cpu, o, old_pc, g): g[o.rt] = cpu.core.bus.read_u16(g[o.rs] + o.simm)
def _h_LW(cpu, o, old_pc, g): g[o.rt] = sx32_to_64(cpu.core.bus.read_u32(g[o.rs] + o.simm))
def _h_LWU(cpu, o, old_pc, g): g[o.rt] = cpu.core.bus.read_u32(g[o.rs] + o.simm)
def _h_LD(cpu, o, old_pc, g): g[o.rt] = cpu.core.bus.read_u64(g[o.rs] + o.simm)
def _h_LWL(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 3; al = addr & ~3
    val = cpu.core.bus.read_u32(al)
    g[o.rt] = sx32_to_64((u32(g[o.rt]) & _lwl_mask[off]) | (val << _lwl_shift[off]))
def _h_LWR(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 3; al = addr & ~3
    val = cpu.core.bus.read_u32(al)
    g[o.rt] = sx32_to_64((u32(g[o.rt]) & _lwr_mask[off]) | (val >> _lwr_shift[off]))
def _h_LDL(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 7; al = addr & ~7
    val = cpu.core.bus.read_u64(al)
    g[o.rt] = (g[o.rt] & _ldl_mask[off]) | (val << _ldl_shift[off])
def _h_LDR(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 7; al = addr & ~7
    val = cpu.core.bus.read_u64(al)
    g[o.rt] = (g[o.rt] & _ldr_mask[off]) | (val >> _ldr_shift[off])
def _h_LL(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); g[o.rt] = sx32_to_64(cpu.core.bus.read_u32(addr))
    cpu.llbit = True; cpu.lladdr = addr & ~3
def _h_LLD(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); g[o.rt] = cpu.core.bus.read_u64(addr)
    cpu.llbit = True; cpu.lladdr = addr & ~7
def _h_LWC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    addr = u32(g[o.rs] + o.simm)
    cpu.fpr[o.rt] = u64((cpu.fpr[o.rt] & 0xFFFFFFFF00000000) | (cpu.core.bus.read_u32(addr) & MASK_32))
def _h_LDC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    cpu.fpr[o.rt] = cpu.core.bus.read_u64(u32(g[o.rs] + o.simm))
def _h_SB(cpu, o, old_pc, g): cpu.core.bus.write_u8(u32(g[o.rs] + o.simm), u8(g[o.rt]))
def _h_SH(cpu, o, old_pc, g): cpu.core.bus.write_u16(u32(g[o.rs] + o.simm), u16(g[o.rt]))
def _h_SW(cpu, o, old_pc, g): cpu.core.bus.write_u32(u32(g[o.rs] + o.simm), u32(g[o.rt]))
def _h_SD(cpu, o, old_pc, g): cpu.core.bus.write_u64(u32(g[o.rs] + o.simm), g[o.rt])
def _h_SWL(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 3; al = addr & ~3
    val = cpu.core.bus.read_u32(al)
    val = (val & _swl_mask[off]) | (u32(g[o.rt]) >> _swl_shift[off])
    cpu.core.bus.write_u32(al, val)
def _h_SWR(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 3; al = addr & ~3
    val = cpu.core.bus.read_u32(al)
    val = (val & _swr_mask[off]) | (u32(g[o.rt]) << _swr_shift[off])
    cpu.core.bus.write_u32(al, val)
def _h_SDL(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 7; al = addr & ~7
    val = cpu.core.bus.read_u64(al)
    val = (val & _sdl_mask[off]) | (g[o.rt] >> _sdl_shift[off])
    cpu.core.bus.write_u64(al, val)
def _h_SDR(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm); off = addr & 7; al = addr & ~7
    val = cpu.core.bus.read_u64(al)
    val = (val & _sdr_mask[off]) | (g[o.rt] << _sdr_shift[off])
    cpu.core.bus.write_u64(al, val)
def _h_SC(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm)
    if cpu.llbit and (addr & ~3) == cpu.lladdr:
        cpu.core.bus.write_u32(addr, u32(g[o.rt])); g[o.rt] = 1
    else: g[o.rt] = 0
    cpu.llbit = False
def _h_SCD(cpu, o, old_pc, g):
    addr = u32(g[o.rs] + o.simm)
    if cpu.llbit and (addr & ~7) == cpu.lladdr:
        cpu.core.bus.write_u64(addr, g[o.rt]); g[o.rt] = 1
    else: g[o.rt] = 0
    cpu.llbit = False
def _h_SWC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    cpu.core.bus.write_u32(u32(g[o.rs] + o.simm), u32(cpu.fpr[o.rt]))
def _h_SDC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    cpu.core.bus.write_u64(u32(g[o.rs] + o.simm), cpu.fpr[o.rt])

# SPECIAL opcodes
def _h_SLL(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rt]) << o.sa)
def _h_SRL(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rt]) >> o.sa)
def _h_SRA(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(sign32(g[o.rt]) >> o.sa)
def _h_SLLV(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rt]) << (g[o.rs] & 0x1F))
def _h_SRLV(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rt]) >> (g[o.rs] & 0x1F))
def _h_SRAV(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(sign32(g[o.rt]) >> (g[o.rs] & 0x1F))
def _h_DSLLV(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rt] << (g[o.rs] & 0x3F))
def _h_DSRLV(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rt] >> (g[o.rs] & 0x3F))
def _h_DSRAV(cpu, o, old_pc, g): g[o.rd] = u64(sign64(g[o.rt]) >> (g[o.rs] & 0x3F))
def _h_DSLL(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rt] << o.sa)
def _h_DSRL(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rt] >> o.sa)
def _h_DSRA(cpu, o, old_pc, g): g[o.rd] = u64(sign64(g[o.rt]) >> o.sa)
def _h_DSLL32(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rt] << (o.sa + 32))
def _h_DSRL32(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rt] >> (o.sa + 32))
def _h_DSRA32(cpu, o, old_pc, g): g[o.rd] = u64(sign64(g[o.rt]) >> (o.sa + 32))
def _h_ADD(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rs] + g[o.rt]))
def _h_ADDU(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rs] + g[o.rt]))
def _h_SUB(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rs] - g[o.rt]))
def _h_SUBU(cpu, o, old_pc, g): g[o.rd] = sx32_to_64(u32(g[o.rs] - g[o.rt]))
def _h_DADD(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] + g[o.rt])
def _h_DADDU(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] + g[o.rt])
def _h_DSUB(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] - g[o.rt])
def _h_DSUBU(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] - g[o.rt])
def _h_AND(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] & g[o.rt])
def _h_OR(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] | g[o.rt])
def _h_XOR(cpu, o, old_pc, g): g[o.rd] = u64(g[o.rs] ^ g[o.rt])
def _h_NOR(cpu, o, old_pc, g): g[o.rd] = u64(~(g[o.rs] | g[o.rt]))
def _h_MOVZ(cpu, o, old_pc, g):
    if g[o.rt] == 0: g[o.rd] = g[o.rs]
def _h_MOVN(cpu, o, old_pc, g):
    if g[o.rt] != 0: g[o.rd] = g[o.rs]
def _h_SLT(cpu, o, old_pc, g): g[o.rd] = 1 if sign64(g[o.rs]) < sign64(g[o.rt]) else 0
def _h_SLTU(cpu, o, old_pc, g): g[o.rd] = 1 if g[o.rs] < g[o.rt] else 0
def _h_MFHI(cpu, o, old_pc, g): g[o.rd] = cpu.hi
def _h_MTHI(cpu, o, old_pc, g): cpu.hi = u64(g[o.rs])
def _h_MFLO(cpu, o, old_pc, g): g[o.rd] = cpu.lo
def _h_MTLO(cpu, o, old_pc, g): cpu.lo = u64(g[o.rs])
def _h_MULT(cpu, o, old_pc, g):
    prod = sign32(g[o.rs]) * sign32(g[o.rt])
    cpu.lo = sx32_to_64(prod & MASK_32); cpu.hi = sx32_to_64((prod >> 32) & MASK_32)
def _h_MULTU(cpu, o, old_pc, g):
    prod = u32(g[o.rs]) * u32(g[o.rt])
    cpu.lo = sx32_to_64(prod & MASK_32); cpu.hi = sx32_to_64((prod >> 32) & MASK_32)
def _h_DMULT(cpu, o, old_pc, g):
    prod = sign64(g[o.rs]) * sign64(g[o.rt]); cpu.lo = u64(prod); cpu.hi = u64(prod >> 64)
def _h_DMULTU(cpu, o, old_pc, g):
    prod = g[o.rs] * g[o.rt]; cpu.lo = u64(prod); cpu.hi = u64(prod >> 64)
def _h_DIV(cpu, o, old_pc, g):
    a_s = sign32(g[o.rs]); b_s = sign32(g[o.rt]); b = u32(g[o.rt])
    if b != 0:
        if a_s == -0x80000000 and b_s == -1: cpu.lo = sx32_to_64(-0x80000000); cpu.hi = 0
        else: cpu.lo = sx32_to_64(a_s // b_s); cpu.hi = sx32_to_64(a_s % b_s)
    else: cpu.lo = 1 if a_s < 0 else -1; cpu.hi = sx32_to_64(a_s)
def _h_DIVU(cpu, o, old_pc, g):
    a = u32(g[o.rs]); b = u32(g[o.rt])
    if b != 0: cpu.lo = sx32_to_64(a // b); cpu.hi = sx32_to_64(a % b)
    else: cpu.lo = -1; cpu.hi = sx32_to_64(a)
def _h_DDIV(cpu, o, old_pc, g):
    a = g[o.rs]; b = g[o.rt]
    if b != 0: cpu.lo = u64(sign64(a) // sign64(b)); cpu.hi = u64(sign64(a) % sign64(b))
    else: cpu.lo = 1 if sign64(a) < 0 else -1; cpu.hi = u64(a)
def _h_DDIVU(cpu, o, old_pc, g):
    a = g[o.rs]; b = g[o.rt]
    if b != 0: cpu.lo = u64(a // b); cpu.hi = u64(a % b)
    else: cpu.lo = -1; cpu.hi = u64(a)

# REGIMM
def _h_BLTZ(cpu, o, old_pc, g):
    if sign64(g[o.rs]) < 0: cpu._branch(o.branch_addr(old_pc))
def _h_BGEZ(cpu, o, old_pc, g):
    if sign64(g[o.rs]) >= 0: cpu._branch(o.branch_addr(old_pc))
def _h_BLTZL(cpu, o, old_pc, g):
    if sign64(g[o.rs]) < 0: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_BGEZL(cpu, o, old_pc, g):
    if sign64(g[o.rs]) >= 0: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_BLTZAL(cpu, o, old_pc, g):
    g[31] = u64(old_pc + 8)
    if sign64(g[o.rs]) < 0: cpu._branch(o.branch_addr(old_pc))
def _h_BGEZAL(cpu, o, old_pc, g):
    g[31] = u64(old_pc + 8)
    if sign64(g[o.rs]) >= 0: cpu._branch(o.branch_addr(old_pc))
def _h_BLTZALL(cpu, o, old_pc, g):
    g[31] = u64(old_pc + 8)
    if sign64(g[o.rs]) < 0: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_BGEZALL(cpu, o, old_pc, g):
    g[31] = u64(old_pc + 8)
    if sign64(g[o.rs]) >= 0: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_J(cpu, o, old_pc, g): cpu._branch(o.target_addr(old_pc))
def _h_JAL(cpu, o, old_pc, g):
    g[31] = u64(old_pc + 8); cpu._branch(o.target_addr(old_pc))
def _h_JR(cpu, o, old_pc, g): cpu._branch(g[o.rs])
def _h_JALR(cpu, o, old_pc, g):
    g[o.rd] = u64(old_pc + 8); cpu._branch(g[o.rs])
def _h_BEQ(cpu, o, old_pc, g):
    if g[o.rs] == g[o.rt]: cpu._branch(o.branch_addr(old_pc))
def _h_BNE(cpu, o, old_pc, g):
    if g[o.rs] != g[o.rt]: cpu._branch(o.branch_addr(old_pc))
def _h_BLEZ(cpu, o, old_pc, g):
    if sign64(g[o.rs]) <= 0: cpu._branch(o.branch_addr(old_pc))
def _h_BGTZ(cpu, o, old_pc, g):
    if sign64(g[o.rs]) > 0: cpu._branch(o.branch_addr(old_pc))
def _h_BEQL(cpu, o, old_pc, g):
    if g[o.rs] == g[o.rt]: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_BNEL(cpu, o, old_pc, g):
    if g[o.rs] != g[o.rt]: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_BLEZL(cpu, o, old_pc, g):
    if sign64(g[o.rs]) <= 0: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()
def _h_BGTZL(cpu, o, old_pc, g):
    if sign64(g[o.rs]) > 0: cpu._branch(o.branch_addr(old_pc))
    else: cpu._skip_likely()

# COP0
def _h_MFC0(cpu, o, old_pc, g): g[o.rt] = sx32_to_64(cpu.cp0[o.rd])
def _h_DMFC0(cpu, o, old_pc, g): g[o.rt] = u64(cpu.cp0[o.rd])
def _h_CFC0(cpu, o, old_pc, g): g[o.rt] = sx32_to_64(cpu.cp0[o.rd])
def _h_MTC0(cpu, o, old_pc, g):
    val = u32(g[o.rt]); rd = o.rd
    if rd == CP0_INDEX: cpu.cp0[rd] = val & 0x8000003F
    elif rd in (CP0_ENTRYLO0, CP0_ENTRYLO1): cpu.cp0[rd] = val & 0x3FFFFFFF
    elif rd == CP0_PAGEMASK: cpu.cp0[rd] = val & 0x01FFE000
    elif rd == CP0_WIRED: cpu.cp0[rd] = val & 0x3F; cpu.cp0[CP0_RANDOM] = 31
    elif rd == CP0_CONTEXT: cpu.cp0[rd] = (cpu.cp0[rd] & 0x7FFFFF) | (val & 0xFF800000)
    elif rd == CP0_COUNT: cpu.cp0[rd] = val
    elif rd == CP0_COMPARE: cpu.cp0[rd] = val; cpu.cp0[CP0_CAUSE] &= ~(1 << 15)
    elif rd in (CP0_ENTRYHI, CP0_STATUS, CP0_CAUSE, CP0_EPC, CP0_ERROREPC, CP0_LLADDR, CP0_CONFIG): cpu.cp0[rd] = val
    elif rd in (28, 29): cpu.cp0[rd] = val
def _h_DMTC0(cpu, o, old_pc, g):
    val = u64(g[o.rt]); rd = o.rd
    if rd == CP0_ENTRYHI: cpu.cp0[rd] = val & 0xFFFFFFFF
    elif rd == CP0_CONTEXT: cpu.cp0[rd] = (cpu.cp0[rd] & 0x7FFFFF) | (val & 0xFFFFFFFFFF800000)
    else: cpu.cp0[rd] = val
def _h_CTC0(cpu, o, old_pc, g): cpu.cp0[o.rd] = u32(g[o.rt])
def _h_BC0(cpu, o, old_pc, g):
    tf = o.rt & 1; likely = bool(o.rt & 2)
    if False == bool(tf): cpu._branch(o.branch_addr(old_pc))
    elif likely: cpu._skip_likely()
def _h_ERET(cpu, o, old_pc, g):
    if cpu.cp0[CP0_STATUS] & STATUS_ERL:
        target = cpu.cp0[CP0_ERROREPC]
        cpu.cp0[CP0_STATUS] &= ~STATUS_ERL
    else:
        target = cpu.cp0[CP0_EPC]
        cpu.cp0[CP0_STATUS] &= ~STATUS_EXL
    cpu.pc = u32(target); cpu.next_pc = u32(cpu.pc + 4)
def _h_TLBWI(cpu, o, old_pc, g): cpu._write_tlb_entry(cpu.cp0[CP0_INDEX] & 0x1F)
def _h_TLBWR(cpu, o, old_pc, g):
    w = cpu.cp0[CP0_WIRED] & 0x1F; cpu._write_tlb_entry(random.randint(w, 31))
def _h_TLBP(cpu, o, old_pc, g):
    hi = cpu.cp0[CP0_ENTRYHI]; vpn2 = (hi >> 13) & 0x7FFFF; asid = hi & 0xFF
    match_i = -1
    for i, entry in enumerate(cpu.tlb):
        if entry.vpn2 == vpn2 and (entry.g or entry.asid == asid): match_i = i; break
    cpu.cp0[CP0_INDEX] = match_i if match_i >= 0 else 0x80000000
def _h_TLBR(cpu, o, old_pc, g):
    idx = cpu.cp0[CP0_INDEX] & 0x1F; entry = cpu.tlb[idx]
    cpu.cp0[CP0_PAGEMASK] = entry.mask; cpu.cp0[CP0_ENTRYHI] = (entry.vpn2 << 13) | entry.asid
    cpu.cp0[CP0_ENTRYLO0] = (entry.pfn0 << 6) | (entry.c0 << 3) | (entry.d0 << 2) | (entry.v0 << 1) | entry.g
    cpu.cp0[CP0_ENTRYLO1] = (entry.pfn1 << 6) | (entry.c1 << 3) | (entry.d1 << 2) | (entry.v1 << 1) | entry.g

# COP1
def _h_MFC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    g[o.rt] = sx32_to_64(cpu.fpr[o.rd] & MASK_32)
def _h_DMFC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    g[o.rt] = cpu.fpr[o.rd]
def _h_CFC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    g[o.rt] = sx32_to_64(cpu.fcr31 if o.rd == 31 else cpu.fcr0)
def _h_MTC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    cpu.fpr[o.rd] = u64((cpu.fpr[o.rd] & 0xFFFFFFFF00000000) | (g[o.rt] & MASK_32))
def _h_DMTC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    cpu.fpr[o.rd] = g[o.rt]
def _h_CTC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    if o.rd == 31: cpu.fcr31 = u32(g[o.rt])
    elif o.rd == 0: cpu.fcr0 = u32(g[o.rt])
def _h_BC1(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    tf = o.rt & 1; likely = bool(o.rt & 2)
    cond = bool((cpu.fcr31 >> FCR31_COND_BIT) & 1)
    if cond == bool(tf): cpu._branch(o.branch_addr(old_pc))
    elif likely: cpu._skip_likely()

# Traps
def _h_SYSCALL(cpu, o, old_pc, g): cpu._raise_exception(8, old_pc)
def _h_BREAK(cpu, o, old_pc, g): cpu._raise_exception(9, old_pc)
def _h_TGE(cpu, o, old_pc, g):
    if sign64(g[o.rs]) >= sign64(g[o.rt]): cpu._raise_exception(13, old_pc)
def _h_TGEU(cpu, o, old_pc, g):
    if g[o.rs] >= g[o.rt]: cpu._raise_exception(13, old_pc)
def _h_TLT(cpu, o, old_pc, g):
    if sign64(g[o.rs]) < sign64(g[o.rt]): cpu._raise_exception(13, old_pc)
def _h_TLTU(cpu, o, old_pc, g):
    if g[o.rs] < g[o.rt]: cpu._raise_exception(13, old_pc)
def _h_TEQ(cpu, o, old_pc, g):
    if g[o.rs] == g[o.rt]: cpu._raise_exception(13, old_pc)
def _h_TNE(cpu, o, old_pc, g):
    if g[o.rs] != g[o.rt]: cpu._raise_exception(13, old_pc)
def _h_TGEI(cpu, o, old_pc, g):
    if sign64(g[o.rs]) >= o.simm: cpu._raise_exception(13, old_pc)
def _h_TGEIU(cpu, o, old_pc, g):
    if g[o.rs] >= u64(o.simm): cpu._raise_exception(13, old_pc)
def _h_TLTI(cpu, o, old_pc, g):
    if sign64(g[o.rs]) < o.simm: cpu._raise_exception(13, old_pc)
def _h_TLTIU(cpu, o, old_pc, g):
    if g[o.rs] < u64(o.simm): cpu._raise_exception(13, old_pc)
def _h_TEQI(cpu, o, old_pc, g):
    if g[o.rs] == u64(o.simm): cpu._raise_exception(13, old_pc)
def _h_TNEI(cpu, o, old_pc, g):
    if g[o.rs] != u64(o.simm): cpu._raise_exception(13, old_pc)

# FPU format ops
def _h_FPU(cpu, o, old_pc, g):
    if not cpu._test_cop1_usable(): cpu._raise_exception(11, old_pc); return
    cpu._clear_fp_cause()
    fmt_id = (o.instr_id >> 6) & 3; funct = o.instr_id & 0x3F
    fs, fd, ft = o.rd, o.sa, o.rt
    if fmt_id == _ID_FPU_S:
        if funct == 0x20: cpu.fpr[fd] = u64((cpu.fpr[fd] & 0xFFFFFFFF00000000) | (cpu.fpr[fs] & MASK_32))
        elif funct == 0x21: cpu.fpr[fd] = f64_to_bits(bits_to_f32(cpu.fpr[fs] & MASK_32))
        elif funct in (0x24, 0x25):
            f = bits_to_f32(cpu.fpr[fs] & MASK_32); w = 0 if math.isnan(f) or math.isinf(f) else int(f)
            cpu.fpr[fd] = u64(w) if funct == 0x25 else u64((cpu.fpr[fd] & 0xFFFFFFFF00000000) | u32(w))
        elif funct == 0x00:
            a,b = bits_to_f32(cpu.fpr[fs]&MASK_32), bits_to_f32(cpu.fpr[ft]&MASK_32)
            cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(a+b))
        elif funct == 0x01:
            a,b = bits_to_f32(cpu.fpr[fs]&MASK_32), bits_to_f32(cpu.fpr[ft]&MASK_32)
            cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(a-b))
        elif funct == 0x02:
            a,b = bits_to_f32(cpu.fpr[fs]&MASK_32), bits_to_f32(cpu.fpr[ft]&MASK_32)
            cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(a*b))
        elif funct == 0x03:
            a,b = bits_to_f32(cpu.fpr[fs]&MASK_32), bits_to_f32(cpu.fpr[ft]&MASK_32)
            if b == 0.0: cpu._set_fp_cause(FCR31_CAUSE_DIVBYZERO); cpu._set_fp_flags(FCR31_CAUSE_DIVBYZERO)
            cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(a/b))
        elif funct == 0x04:
            f = bits_to_f32(cpu.fpr[fs]&MASK_32)
            cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(math.sqrt(f) if f>=0 else float('nan')))
        elif funct == 0x05:
            f = bits_to_f32(cpu.fpr[fs]&MASK_32); cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(abs(f)))
        elif funct == 0x06: cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|(cpu.fpr[fs]&MASK_32))
        elif funct == 0x07:
            f = bits_to_f32(cpu.fpr[fs]&MASK_32); cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(-f))
        elif funct in (0x0C,0x0D,0x0E,0x0F):
            f = bits_to_f32(cpu.fpr[fs]&MASK_32)
            r = 0 if (math.isnan(f) or math.isinf(f)) else (int(round(f)) if funct==0x0C else (int(f) if funct==0x0D else int(math.ceil(f)) if funct==0x0E else int(math.floor(f))))
            cpu.fpr[fd] = u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|u32(r))
        elif funct in (0x08,0x09,0x0A,0x0B):
            f = bits_to_f32(cpu.fpr[fs]&MASK_32)
            r = int(f) if math.isinf(f) else (0 if math.isnan(f) else (int(round(f)) if funct==0x08 else (int(f) if funct==0x09 else int(math.ceil(f)) if funct==0x0A else int(math.floor(f)))))
            cpu.fpr[fd] = u64(r)
        elif funct >= 0x30:
            a,b = bits_to_f32(cpu.fpr[fs]&MASK_32), bits_to_f32(cpu.fpr[ft]&MASK_32)
            cond = False
            if funct==0x30: cond=False
            elif funct in (0x31,0x33,0x35,0x37,0x39,0x3B,0x3F,0x3D): cond=math.isnan(a) or math.isnan(b)
            elif funct in (0x32,0x3A): cond=not math.isnan(a) and not math.isnan(b) and a==b
            elif funct in (0x34,0x3C): cond=not math.isnan(a) and not math.isnan(b) and a<b
            elif funct in (0x36,0x3E): cond=not math.isnan(a) and not math.isnan(b) and a<=b
            elif funct==0x38: cond=False
            if cond: cpu.fcr31 |= (1 << FCR31_COND_BIT)
            else: cpu.fcr31 &= ~(1 << FCR31_COND_BIT)
    elif fmt_id == _ID_FPU_D:
        fs_v, ft_v = cpu.fpr[fs], cpu.fpr[ft]
        if funct == 0x00: cpu.fpr[fd] = f64_to_bits(bits_to_f64(fs_v)+bits_to_f64(ft_v))
        elif funct == 0x01: cpu.fpr[fd] = f64_to_bits(bits_to_f64(fs_v)-bits_to_f64(ft_v))
        elif funct == 0x02: cpu.fpr[fd] = f64_to_bits(bits_to_f64(fs_v)*bits_to_f64(ft_v))
        elif funct == 0x03:
            d = bits_to_f64(ft_v)
            if d==0.0: cpu._set_fp_cause(FCR31_CAUSE_DIVBYZERO)
            cpu.fpr[fd] = f64_to_bits(bits_to_f64(fs_v)/d)
        elif funct == 0x04:
            f=bits_to_f64(fs_v); cpu.fpr[fd]=f64_to_bits(math.sqrt(f) if f>=0 else float('nan'))
        elif funct == 0x05: cpu.fpr[fd]=f64_to_bits(abs(bits_to_f64(fs_v)))
        elif funct == 0x06: cpu.fpr[fd]=fs_v
        elif funct == 0x07: cpu.fpr[fd]=f64_to_bits(-bits_to_f64(fs_v))
        elif funct in (0x24,0x25):
            f=bits_to_f64(fs_v); w=0 if math.isnan(f) or math.isinf(f) else int(f)
            cpu.fpr[fd]=u64(w) if funct==0x25 else u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|u32(w))
        elif funct in (0x0C,0x0D,0x0E,0x0F):
            f=bits_to_f64(fs_v); r=0 if (math.isnan(f) or math.isinf(f)) else (int(round(f)) if funct==0x0C else (int(f) if funct==0x0D else int(math.ceil(f)) if funct==0x0E else int(math.floor(f))))
            cpu.fpr[fd]=u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|u32(r))
        elif funct in (0x08,0x09,0x0A,0x0B):
            f=bits_to_f64(fs_v); r=int(f) if math.isinf(f) else (0 if math.isnan(f) else (int(round(f)) if funct==0x08 else (int(f) if funct==0x09 else int(math.ceil(f)) if funct==0x0A else int(math.floor(f)))))
            cpu.fpr[fd]=u64(r)
        elif funct >= 0x30:
            a,b=bits_to_f64(fs_v),bits_to_f64(ft_v); cond=False
            if funct in (0x31,0x33,0x35,0x37,0x39,0x3B,0x3F,0x3D): cond=math.isnan(a) or math.isnan(b)
            elif funct in (0x32,0x3A): cond=not math.isnan(a) and not math.isnan(b) and a==b
            elif funct in (0x34,0x3C): cond=not math.isnan(a) and not math.isnan(b) and a<b
            elif funct in (0x36,0x3E): cond=not math.isnan(a) and not math.isnan(b) and a<=b
            if cond: cpu.fcr31 |= (1 << FCR31_COND_BIT)
            else: cpu.fcr31 &= ~(1 << FCR31_COND_BIT)
    elif fmt_id == _ID_FPU_W:
        fv=bits_to_f32(cpu.fpr[fs]&MASK_32)
        if funct==0x20: cpu.fpr[fd]=u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(float(fv)))
        elif funct==0x21: cpu.fpr[fd]=f64_to_bits(float(fv))
        elif funct==0x24: cpu.fpr[fd]=u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|u32(int(fv)))
        elif funct==0x25: cpu.fpr[fd]=u64(int(fv))
    elif fmt_id == _ID_FPU_L:
        fv=bits_to_f64(cpu.fpr[fs])
        if funct==0x20: cpu.fpr[fd]=u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|f32_to_bits(float(fv)))
        elif funct==0x21: cpu.fpr[fd]=f64_to_bits(float(fv))
        elif funct in (0x24,0x25):
            w=0 if math.isnan(fv) or math.isinf(fv) else int(fv)
            cpu.fpr[fd]=u64(w) if funct==0x25 else u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|u32(w))
        elif funct in (0x0C,0x0D,0x0E,0x0F):
            r=0 if (math.isnan(fv) or math.isinf(fv)) else (int(round(fv)) if funct==0x0C else (int(fv) if funct==0x0D else int(math.ceil(fv)) if funct==0x0E else int(math.floor(fv))))
            cpu.fpr[fd]=u64((cpu.fpr[fd]&0xFFFFFFFF00000000)|u32(r))
        elif funct in (0x08,0x09,0x0A,0x0B):
            r=int(fv) if math.isinf(fv) else (0 if math.isnan(fv) else (int(round(fv)) if funct==0x08 else (int(fv) if funct==0x09 else int(math.ceil(fv)) if funct==0x0A else int(math.floor(fv)))))
            cpu.fpr[fd]=u64(r)
        elif funct>=0x30:
            cond=False
            if funct in (0x31,0x33,0x35,0x37,0x39,0x3B,0x3F,0x3D): cond=math.isnan(fv) or math.isnan(bits_to_f64(cpu.fpr[ft]))
            elif funct in (0x32,0x3A): cond=not math.isnan(fv) and not math.isnan(bits_to_f64(cpu.fpr[ft])) and fv==bits_to_f64(cpu.fpr[ft])
            elif funct in (0x34,0x3C): cond=not math.isnan(fv) and not math.isnan(bits_to_f64(cpu.fpr[ft])) and fv<bits_to_f64(cpu.fpr[ft])
            elif funct in (0x36,0x3E): cond=not math.isnan(fv) and not math.isnan(bits_to_f64(cpu.fpr[ft])) and fv<=bits_to_f64(cpu.fpr[ft])
            if cond: cpu.fcr31 |= (1 << FCR31_COND_BIT)
            else: cpu.fcr31 &= ~(1 << FCR31_COND_BIT)

def _h_CACHE(cpu, o, old_pc, g): pass

# PRIMARY
for _op,_fn in [
    (0x02,_h_J),(0x03,_h_JAL),(0x04,_h_BEQ),(0x05,_h_BNE),(0x06,_h_BLEZ),(0x07,_h_BGTZ),
    (0x08,_h_ADDI),(0x09,_h_ADDIU),(0x0A,_h_SLTI),(0x0B,_h_SLTIU),(0x0C,_h_ANDI),(0x0D,_h_ORI),(0x0E,_h_XORI),(0x0F,_h_LUI),
    (0x14,_h_BEQL),(0x15,_h_BNEL),(0x16,_h_BLEZL),(0x17,_h_BGTZL),
    (0x18,_h_DADDI),(0x19,_h_DADDIU),(0x1A,_h_LDL),(0x1B,_h_LDR),
    (0x20,_h_LB),(0x21,_h_LH),(0x22,_h_LWL),(0x23,_h_LW),(0x24,_h_LBU),(0x25,_h_LHU),(0x26,_h_LWR),(0x27,_h_LWU),
    (0x28,_h_SB),(0x29,_h_SH),(0x2A,_h_SWL),(0x2B,_h_SW),(0x2C,_h_SDL),(0x2D,_h_SDR),(0x2E,_h_SWR),(0x2F,_h_CACHE),
    (0x30,_h_LL),(0x31,_h_LWC1),(0x32,_h_NOP),(0x33,_h_NOP),(0x34,_h_LLD),(0x35,_h_LDC1),(0x36,_h_NOP),(0x37,_h_LD),
    (0x38,_h_SC),(0x39,_h_SWC1),(0x3A,_h_NOP),(0x3B,_h_NOP),(0x3C,_h_SCD),(0x3D,_h_SDC1),(0x3E,_h_NOP),(0x3F,_h_SD),
]: _DISPATCH[_ID_PRIMARY|_op] = _fn
# SPECIAL
for _f,_fn in [
    (0x00,_h_SLL),(0x02,_h_SRL),(0x03,_h_SRA),(0x04,_h_SLLV),(0x06,_h_SRLV),(0x07,_h_SRAV),
    (0x08,_h_JR),(0x09,_h_JALR),(0x0A,_h_MOVZ),(0x0B,_h_MOVN),(0x0C,_h_SYSCALL),(0x0D,_h_BREAK),(0x0F,_h_NOP),
    (0x10,_h_MFHI),(0x11,_h_MTHI),(0x12,_h_MFLO),(0x13,_h_MTLO),
    (0x14,_h_DSLLV),(0x16,_h_DSRLV),(0x17,_h_DSRAV),
    (0x18,_h_MULT),(0x19,_h_MULTU),(0x1A,_h_DIV),(0x1B,_h_DIVU),(0x1C,_h_DMULT),(0x1D,_h_DMULTU),(0x1E,_h_DDIV),(0x1F,_h_DDIVU),
    (0x20,_h_ADD),(0x21,_h_ADDU),(0x22,_h_SUB),(0x23,_h_SUBU),(0x24,_h_AND),(0x25,_h_OR),(0x26,_h_XOR),(0x27,_h_NOR),
    (0x2A,_h_SLT),(0x2B,_h_SLTU),(0x2C,_h_DADD),(0x2D,_h_DADDU),(0x2E,_h_DSUB),(0x2F,_h_DSUBU),
    (0x30,_h_TGE),(0x31,_h_TGEU),(0x32,_h_TLT),(0x33,_h_TLTU),(0x34,_h_TEQ),(0x36,_h_TNE),
    (0x38,_h_DSLL),(0x3A,_h_DSRL),(0x3B,_h_DSRA),(0x3C,_h_DSLL32),(0x3E,_h_DSRL32),(0x3F,_h_DSRA32),
]: _DISPATCH[_ID_SPECIAL|_f] = _fn
# REGIMM
for _rt,_fn in [
    (0x00,_h_BLTZ),(0x01,_h_BGEZ),(0x02,_h_BLTZL),(0x03,_h_BGEZL),
    (0x08,_h_TGEI),(0x09,_h_TGEIU),(0x0A,_h_TLTI),(0x0B,_h_TLTIU),(0x0C,_h_TEQI),(0x0E,_h_TNEI),
    (0x10,_h_BLTZAL),(0x11,_h_BGEZAL),(0x12,_h_BLTZALL),(0x13,_h_BGEZALL),
]: _DISPATCH[_ID_REGIMM|_rt] = _fn
# COP0_RS
for _rs,_fn in [
    (0x00,_h_MFC0),(0x01,_h_DMFC0),(0x02,_h_CFC0),(0x04,_h_MTC0),(0x05,_h_DMTC0),(0x06,_h_CTC0),(0x08,_h_BC0),
]: _DISPATCH[_ID_COP0_RS|_rs] = _fn
# COP0_CO
for _cof,_fn in [
    (0x01,_h_TLBR),(0x02,_h_TLBWI),(0x06,_h_TLBWR),(0x08,_h_TLBP),(0x18,_h_ERET),
]: _DISPATCH[_ID_COP0_CO|_cof] = _fn
# COP1_RS
for _rs,_fn in [
    (0x00,_h_MFC1),(0x01,_h_DMFC1),(0x02,_h_CFC1),(0x04,_h_MTC1),(0x05,_h_DMTC1),(0x06,_h_CTC1),(0x08,_h_BC1),
]: _DISPATCH[_ID_COP1_RS|_rs] = _fn
# FPU (all format+funct combos go to _h_FPU)
for _fid in (_ID_FPU_S,_ID_FPU_D,_ID_FPU_W,_ID_FPU_L):
    for _f in range(64):
        _DISPATCH[_ID_FPU|(_fid<<6)|_f] = _h_FPU
# NOP for any unmapped primary op (LWC2, SWC2, LDC2, SDC2, etc)
for _op in (0x12,0x13,0x1C,0x1D,0x1E,0x1F):
    _DISPATCH[_ID_PRIMARY|_op] = _h_CACHE


# ── ACsN64Core — full emulator core ──
class ACsN64Core:
    def __init__(self):
        self.rdram = bytearray(RDRAM_SIZE)
        self.rom = bytearray()
        self.rom_path = ""
        self.rom_header:Optional[N64Header]=None
        self.cic = CIC_NUS_6102
        self.pif_ram = bytearray(PIF_RAM_SIZE)
        self.rsp_dmem = bytearray(RSP_DMEM_SIZE)
        self.rsp_imem = bytearray(RSP_IMEM_SIZE)
        self.rsp_pc = 0
        self.audio_signal = False
        self._vi_origin_set = False
        self.save_mgr = SaveManager()
        self.cheat_engine = CheatEngine()
        self.cpu = CPUCore(self)
        self.bus = DeviceBus(self)
        self.running = False
        self.frame_count = 0
        self.vi_counter = 0
        self.vi_clock = 48682
        self.cycle_count = 0
        self.cycle_limit = 200000
        self.fb_ppm:Optional[bytes]=None
        self.reset()

    def reset(self):
        self.rdram = bytearray(RDRAM_SIZE)
        self.rsp_dmem = bytearray(RSP_DMEM_SIZE)
        self.rsp_imem = bytearray(RSP_IMEM_SIZE)
        self._vi_origin_set = False
        self.vi_counter = 0
        self.frame_count = 0
        self.fb_ppm = None
        seed_pif_ram(self.pif_ram, self.cic)
        self.cpu.reset()
        self.bus.reset()
        self.save_mgr.reset()

    def load_rom(self, path):
        try:
            with open(path, "rb") as f:
                raw = bytearray(f.read())
        except Exception as e:
            return str(e)
        if len(raw) < 0x40:
            return "ROM too small (<64 bytes)"
        norm = normalize_rom_bytes(raw)
        self.rom = bytearray(norm)
        self.rom_path = path
        self.cic = get_cic_chip_id(self.rom)
        self.rom_header = N64Header(self.rom)
        seed_pif_ram(self.pif_ram, self.cic)
        dst = get_rom_region(self.rom)
        ntsc_fix = 48682
        self.vi_clock = ntsc_fix if dst==REGION_NTSC else 49665
        self.cycle_limit = 200000
        self.reset()
        entry = normalize_commercial_entry(self.rom_header.boot_address)
        self.cpu.pc = entry
        self.cpu.next_pc = entry + 4
        self.bus.regs[PI_STATUS] = 0
        self.bus.hw_interrupts = 0
        return None

    def trigger_sp_dma(self, to_rsp:bool):
        sp_mem = self.bus.regs.get(SP_MEM_ADDR, 0) & 0xFFF
        dram = self.bus.regs.get(SP_DRAM_ADDR, 0) & 0x00FFFFFF
        length = self.bus.regs.get(SP_RD_LEN if to_rsp else SP_WR_LEN, 0) & 0xFFF
        if length == 0:
            length = 8
        if to_rsp:
            src = dram + 0 if dram < RDRAM_SIZE else 0
            dst = sp_mem
            data = self.rdram[src:src+length] if src+length <= RDRAM_SIZE else bytearray(length)
            if 0 <= dst < RSP_DMEM_SIZE:
                end = min(dst+length, RSP_DMEM_SIZE)
                self.rsp_dmem[dst:end] = data[:end-dst]
            elif RSP_DMEM_SIZE <= dst < RSP_DMEM_SIZE+RSP_IMEM_SIZE:
                off = dst - RSP_DMEM_SIZE
                end = min(off+length, RSP_IMEM_SIZE)
                self.rsp_imem[off:end] = data[:end-off]
        else:
            dst = dram if dram < RDRAM_SIZE else 0
            src = sp_mem
            if 0 <= src < RSP_DMEM_SIZE:
                data = self.rsp_dmem[src:src+length]
            elif RSP_DMEM_SIZE <= src < RSP_DMEM_SIZE+RSP_IMEM_SIZE:
                off = src - RSP_DMEM_SIZE
                data = self.rsp_imem[off:off+length]
            else:
                data = bytearray(length)
            end = min(dst+length, RDRAM_SIZE)
            self.rdram[dst:end] = data[:end-dst]
        self.bus.hw_interrupts |= MI_INTR_SP

    def trigger_pi_dma(self):
        dram = self.bus.regs.get(PI_DRAM_ADDR, 0) & 0x00FFFFFF
        cart = self.bus.regs.get(PI_CART_ADDR, 0) & MASK_32
        rdlen = self.bus.regs.get(PI_RD_LEN, 0) & 0x00FFFFFF
        wrlen = self.bus.regs.get(PI_WR_LEN, 0) & 0x00FFFFFF
        is_write = wrlen > 0
        length = wrlen if is_write else rdlen
        if length == 0:
            length = 64
        length = (length & 0x00FFFFFE) + 1
        if not is_write:
            ca = cart & 0x1FFFFFFF
            if 0x10000000 <= cart < 0x10000000 + len(self.rom):
                off = cart - 0x10000000
                src = self.rom[off:off+length]
            elif 0x08000000 <= cart < 0x08000000 + len(self.rom):
                off = cart - 0x08000000
                src = self.rom[off:off+length]
            else:
                src = bytearray(min(length, RDRAM_SIZE - dram))
                self.save_mgr.pi_read(ca, length, self.rdram, dram)
                src = self.rdram[dram:dram+length]
            end = min(dram+len(src), RDRAM_SIZE)
            self.rdram[dram:end] = src[:end-dram]
        else:
            self.save_mgr.pi_write(cart & 0x1FFFFFFF, length, self.rdram, dram)
        self.bus.hw_interrupts |= MI_INTR_PI

    def trigger_si_dma(self, read_pif:bool):
        dram = self.bus.regs.get(SI_DRAM_ADDR, 0) & 0x00FFFFFF
        if read_pif:
            for i in range(min(PIF_RAM_SIZE, RDRAM_SIZE - dram)):
                self.rdram[dram + i] = self.pif_ram[i]
        else:
            for i in range(min(PIF_RAM_SIZE, RDRAM_SIZE - dram)):
                self.pif_ram[i] = self.rdram[dram + i]
        self.bus.hw_interrupts |= MI_INTR_SI

    def process_rsp(self):
        pass

    def process_rdp(self):
        pass

    def process_audio(self):
        self.audio_signal = True

    def render_vi(self):
        origin = self.bus.regs.get(VI_ORIGIN, 0)
        if origin == 0:
            return
        width = self.bus.regs.get(VI_WIDTH, 320)
        if width < 16 or width > 640:
            width = 320
        height = 240
        ppm = rdram_rgb5551_to_ppm(self.rdram, origin, width, height)
        if ppm is not None:
            self.fb_ppm = ppm

    def step_frame(self):
        limit = self.cycle_limit
        cycles = 0
        while cycles < limit and self.running:
            self.cpu.step()
            cycles += 1
            self.cycle_count += 1
            self.vi_counter += 1
            if self.vi_counter >= self.vi_clock:
                self.vi_counter = 0
                self.frame_count += 1
                self.bus.half_line = (self.bus.half_line + 1) & 0x3FF
                vint = self.bus.regs.get(VI_INTR, 0x3FF)
                if self.bus.half_line == vint:
                    self.bus.hw_interrupts |= MI_INTR_VI
                if self.bus.half_line >= 262:
                    self.bus.half_line = 0
                    self.cheat_engine.apply(self.bus, self.rdram)
                    if self.frame_count % 3 == 0:
                        self.render_vi()
        self.bus.half_line = 0


# ── Tkinter GUI ──
class ROMBrowser(tk.Frame if tk else object):
    def __init__(self, parent, on_load):
        if not tk: return
        super().__init__(parent, bg=CATHLE_WIN_GRAY)
        self.on_load = on_load
        self.roms:List[Dict[str,Any]] = []
        self.var_romlist:List[Any] = []
        self.listbox:Optional[tk.Listbox] = None
        self._build_ui()
        self.scan_roms()

    def _build_ui(self):
        title = tk.Label(self, text="ROM Browser", font=UI_FONT_BOLD, bg=CATHLE_WIN_GRAY, fg=TEXT_COLOR)
        title.pack(pady=2)
        frm = tk.Frame(self, bg=CATHLE_PANEL_WHITE, bd=1, relief=tk.SUNKEN)
        frm.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        sb = tk.Scrollbar(frm, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(frm, font=UI_FONT_MONO, bg=CATHLE_PANEL_WHITE, fg=TEXT_COLOR,
                                  selectbackground=CATHLE_LIST_SEL_BG, selectforeground=CATHLE_LIST_SEL_FG,
                                  yscrollcommand=sb.set, exportselection=False)
        sb.config(command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self._load_selected())
        btnfrm = tk.Frame(self, bg=CATHLE_WIN_GRAY)
        btnfrm.pack(fill=tk.X, pady=2)
        tk.Button(btnfrm, text="Browse...", font=UI_FONT, command=self._browse_file).pack(side=tk.LEFT, padx=2)
        tk.Button(btnfrm, text="Load", font=UI_FONT, command=self._load_selected).pack(side=tk.LEFT, padx=2)

    def scan_roms(self):
        self.roms.clear()
        self.var_romlist.clear()
        if self.listbox:
            self.listbox.delete(0, tk.END)
        try:
            if not os.path.isdir(_DEFAULT_ROM_DIR):
                return
            entries = sorted(os.listdir(_DEFAULT_ROM_DIR))[:_ROM_SCAN_MAX_FILES]
        except OSError:
            return
        for fname in entries:
            if not fname.lower().endswith(ROM_EXTENSIONS):
                continue
            fpath = os.path.join(_DEFAULT_ROM_DIR, fname)
            try:
                fsize = os.path.getsize(fpath)
                if fsize < 0x40:
                    continue
            except OSError:
                continue
            short = fname if len(fname) <= 50 else fname[:47]+"..."
            display = f"{short:<52}{fsize//1024:>6}K"
            entry = {"file_name": fname, "path": fpath, "size": fsize, "display": display}
            self.roms.append(entry)
            self.var_romlist.append(entry)
            if self.listbox:
                self.listbox.insert(tk.END, display)

    def _load_selected(self):
        if self.listbox:
            sel = self.listbox.curselection()
            if sel and 0 <= sel[0] < len(self.roms):
                self.on_load(self.roms[sel[0]]["path"])

    def _browse_file(self):
        if not filedialog:
            return
        path = filedialog.askopenfilename(filetypes=[("N64 ROM","*.z64;*.v64;*.n64;*.rom;*.bin"),("All","*.*")])
        if path:
            self.on_load(path)


class CathleApp:
    def __init__(self):
        self.core = ACsN64Core()
        self.running = False
        self.emu_thread:Optional[threading.Thread] = None
        self.last_frame_time = 0.0
        self.fps_frames = 0
        self.fps_time = 0.0
        if tk:
            self._build_gui()

    def _build_gui(self):
        self.root = tk.Tk()
        self.status_text = tk.StringVar(value="Ready")
        self.fps_text = tk.StringVar(value="0 FPS")
        self.root.title(WINDOW_TITLE)
        self.root.geometry("640x540")
        self.root.resizable(True, True)
        self.root.configure(bg=CATHLE_WIN_GRAY)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=CATHLE_WIN_GRAY, sashrelief=tk.RAISED, sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True)
        self.browser = ROMBrowser(main_pane, self.load_rom)
        main_pane.add(self.browser, width=200)
        right = tk.Frame(main_pane, bg=CATHLE_PANEL_WHITE)
        main_pane.add(right, width=420)
        self.canvas = tk.Canvas(right, bg=CATHLE_TEXT, width=320, height=240, bd=1, relief=tk.SUNKEN,
                                highlightbackground=CATHLE_VIEWPORT_BORDER)
        self.canvas.pack(pady=4)
        ctrl = tk.Frame(right, bg=CATHLE_WIN_GRAY)
        ctrl.pack(fill=tk.X, pady=2)
        self.btn_start = tk.Button(ctrl, text="Start", font=UI_FONT, command=self.toggle_emu, width=8)
        self.btn_start.pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="Reset", font=UI_FONT, command=self.reset_core, width=8).pack(side=tk.LEFT, padx=2)
        tk.Label(ctrl, textvariable=self.fps_text, font=UI_FONT_MONO, bg=CATHLE_WIN_GRAY, fg=TERMINAL_GREEN).pack(side=tk.RIGHT, padx=4)
        status = tk.Label(self.root, textvariable=self.status_text, font=UI_FONT, bg=CATHLE_WIN_GRAY, fg=TEXT_COLOR,
                          anchor=tk.W, relief=tk.SUNKEN, bd=1)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.root.after(100, self._poll)

    def load_rom(self, path):
        err = self.core.load_rom(path)
        if err:
            if messagebox: messagebox.showerror("Load Error", err)
            self.status_text.set(f"Error: {err}")
            return
        name = os.path.basename(path)
        title = self.core.rom_header.title if self.core.rom_header else "?"
        self.status_text.set(f"Loaded: {name}  [{title}]")
        self.root.title(f"{WINDOW_TITLE} — {name}")

    def toggle_emu(self):
        if self.running:
            self.running = False
            self.btn_start.config(text="Start")
            self.status_text.set("Paused")
        else:
            self.running = True
            self.core.running = True
            self.btn_start.config(text="Stop")
            self.status_text.set("Running")

    def reset_core(self):
        was_running = self.running
        self.running = False
        self.core.running = False
        self.core.reset()
        self.core.rom = bytearray(self.core.rom)
        if self.core.rom_header:
            entry = normalize_commercial_entry(self.core.rom_header.boot_address)
            self.core.cpu.pc = entry
            self.core.cpu.next_pc = entry + 4
        if was_running:
            self.running = True
            self.core.running = True
        self.status_text.set("Reset")

    def _poll(self):
        if self.running and self.core:
            self.core.step_frame()
            if self.core.fb_ppm:
                try:
                    b64 = base64.b64encode(self.core.fb_ppm).decode("ascii")
                    img = tk.PhotoImage(data=b64)
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
                    self.canvas.image = img
                except Exception:
                    pass
            now = time.monotonic()
            self.fps_frames += 1
            if now - self.fps_time >= 1.0:
                self.fps_text.set(f"{self.fps_frames} FPS")
                self.fps_frames = 0
                self.fps_time = now
        self.root.after(16, self._poll)

    def _on_close(self):
        self.running = False
        self.core.running = False
        if self.root:
            self.root.destroy()
            self.root = None

    def run(self):
        if self.root:
            self.root.mainloop()


def main():
    if not tk:
        print("Tkinter not available — running headless test")
        core = ACsN64Core()
        print("cathle 0.1.1 core instantiated (no GUI)")
        return
    app = CathleApp()
    app.run()

if __name__ == "__main__":
    main()

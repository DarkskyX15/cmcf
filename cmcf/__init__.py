"""
MCMF - C to Minecraft Function Compiler

A compiler that converts C to Minecraft mcfunction datapacks,
using LLVM IR as the intermediate representation.

Pipeline: C source -> (clang) -> LLVM IR -> (mcmf) -> mcfunction datapack
"""

__version__ = "0.2.0"

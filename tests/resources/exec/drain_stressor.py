import math
import os
import sys
import time
from typing import BinaryIO

bytes_to_produce = int(sys.argv[1])
mode = sys.argv[2]
do_flush = sys.argv[3] == "flush"

if bytes_to_produce < 0:
    err_msg = "incorrect data_count specified"
    raise ValueError(err_msg)
if bytes_to_produce > 2**32:
    err_msg = "absurdly large data_count specified"
    raise ValueError(err_msg)

assert mode in ["num", "num-", "8k", "8k-"]


def hex_num_newline(i: int) -> str:
    return f"{i:#08x}{os.linesep}"


def hex_num_no_newline(i: int) -> str:
    return f"{i:#08x}"


def line8k_newline(i: int) -> str:
    return line8k_no_newline(i) + os.linesep


def line8k_no_newline(i: int) -> str:
    return hex_num_no_newline(i) * int(8 * 1024 / 8)


match mode:
    case "num":
        gen = hex_num_newline
    case "num-":
        gen = hex_num_no_newline
    case "8k":
        gen = line8k_newline
    case "8k-":
        gen = line8k_no_newline
    case _:
        err_msg = "unsupported mode"
        raise ValueError(err_msg)


def emit_chunk(sink: BinaryIO, data: str, *, flush: bool) -> None:
    sink.write(data.encode("utf-8"))
    if flush:
        sink.flush()


bytes_per_element = len(gen(0))
elements_to_output = math.ceil(bytes_to_produce * 1.0 / bytes_per_element)

bytes_produced = 0
for i in range(elements_to_output):
    # NOTE: we do weird stuff in a weird way.
    # The program inputs a number of BYTES, but we generate text output.
    # This is somewhat intentional, however it has a nasty side effect
    # with respect to line endings. On Windows line ending is "\r\n" - 2 bytes.
    # However, when writing text data, Python translates "\n" to "\r\n"
    # automatically. So we hack around that by writing out data in binary
    # instead.
    data_chunk_stdout = gen(i)
    data_chunk_stderr = gen(elements_to_output - i - 1)

    data_size = len(data_chunk_stdout)
    if bytes_produced + data_size > bytes_to_produce:
        chars_to_emit = bytes_to_produce - bytes_produced
        assert chars_to_emit > 0
        data_chunk_stdout = data_chunk_stdout[:chars_to_emit]
        data_chunk_stderr = data_chunk_stderr[:chars_to_emit]
        bytes_produced += chars_to_emit
    else:
        bytes_produced += data_size

    emit_chunk(sys.stdout.buffer, data_chunk_stdout, flush=do_flush)
    emit_chunk(sys.stderr.buffer, data_chunk_stderr, flush=do_flush)


sys.stdout.close()
os.close(1)
sys.stderr.close()
os.close(2)
time.sleep(1.0)
sys.exit(0)

preamble_byte = 0xAA
preamble_len = 32


with open("preamble.hex", "wb") as f:
    f.write(bytes([preamble_byte]*preamble_len))

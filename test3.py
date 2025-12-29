#!/usr/bin/env python3

import sys


def compare_files(file1, file2, max_diffs=20):
    with open(file1, "rb") as f1, open(file2, "rb") as f2:
        data1 = f1.read()
        data2 = f2.read()

    len1 = len(data1)
    len2 = len(data2)

    print(f"File 1: {file1} ({len1} bytes)")
    print(f"File 2: {file2} ({len2} bytes)")

    if len1 != len2:
        print("⚠️  File sizes differ!")

    min_len = min(len1, len2)
    diffs = []

    for i in range(min_len):
        if data1[i] != data2[i]:
            diffs.append((i, data1[i], data2[i]))
            if len(diffs) >= max_diffs:
                break

    if not diffs and len1 == len2:
        print("✅ Files are identical.")
        return

    print(f"❌ Files differ. Showing up to {max_diffs} differences:\n")
    for idx, b1, b2 in diffs:
        print(f"Offset {idx:6d}: {file1}=0x{b1:02X}, {file2}=0x{b2:02X}")

    if len1 != len2:
        print("\nNote: Comparison stopped at shortest file length.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} original.bin received.bin")
        sys.exit(1)

    compare_files(sys.argv[1], sys.argv[2])

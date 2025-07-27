import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Generate AES key and 96-bit nonce
NONCE = os.urandom(12)
SECRET_KEY = AESGCM.generate_key(bit_length=256)


def obfuscate_key(aes_key: bytes, xor0: list[int], xor3: list[int]):
    assert len(aes_key) == 32, "AES-256 key must be 32 bytes"

    part0 = aes_key[0:8]
    part1 = aes_key[8:16]
    part2 = aes_key[16:24]
    part3 = aes_key[24:32]

    obf0 = [b ^ x for b, x in zip(part0, xor0)]
    obf1 = list(reversed(part1))
    obf2 = list(part2)
    obf3 = [b ^ x for b, x in zip(part3, xor3)]

    return obf0, obf1, obf2, obf3


def random_xor_array(name: str) -> tuple[str, list[int]]:
    values = [secrets.randbelow(256) for _ in range(8)]
    return f"{name} = [{', '.join(f'0x{b:02X}' for b in values)}]", values


def format_array(name: str, data: list[int]) -> str:
    return f"{name} = [{', '.join(f'0x{b:02X}' for b in data)}]"


def generate_obfuscated_key_code(aes_key: bytes) -> str:
    xor0_code, xor0_values = random_xor_array("xor0")
    xor3_code, xor3_values = random_xor_array("xor3")

    obf0, obf1, obf2, obf3 = obfuscate_key(aes_key, xor0_values, xor3_values)

    return f"""
    # Auto-generated AES key reconstruction code

    {format_array("p0", obf0)}
    {format_array("p1", obf1)}
    {format_array("p2", obf2)}
    {format_array("p3", obf3)}
    {xor0_code}
    {xor3_code}

    def get_aes_key() -> bytes:
        key = bytearray(32)
        for i in range(8):
            key[i] = p0[i] ^ xor0[i]
            key[i + 8] = p1[7 - i]
            key[i + 16] = p2[i]
            key[i + 24] = p3[i] ^ xor3[i]
        return bytes(key)

    SECRET_KEY = get_aes_key()
    """


if __name__ == "__main__":
    print(f"AES Key (hex): {SECRET_KEY.hex()}")
    print(generate_obfuscated_key_code(SECRET_KEY))

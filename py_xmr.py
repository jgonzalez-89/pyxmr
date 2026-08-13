#!/usr/bin/env python3
"""
Deriva la clave de gasto de una subdireccion de Monero.

PARA QUE SIRVE
--------------
Si por error se configuro una SUBDIRECCION como si fuera la direccion principal
de una cartera, los pagos acaban en direcciones que la cartera original no
reconoce. Este script calcula la clave de gasto que controla esos fondos, para
poder restaurar una cartera capaz de moverlos.

COMO USARLO  --  LEER ANTES DE EJECUTAR
---------------------------------------
1. Ejecutalo en el ordenador de quien controla la cartera, NUNCA en otro.
2. DESCONECTA LA RED (wifi y cable) antes de introducir las claves.
3. No compartas la salida con nadie: la clave que imprime da control total
   sobre esos fondos.
4. Al terminar, borra este fichero.

Necesitas tres datos, que se obtienen en monero-wallet-cli con la cartera
abierta:

    spendkey    -> "secret spend key"   (64 caracteres hexadecimales)
    viewkey     -> "secret view key"    (64 caracteres hexadecimales)

y el indice de la subdireccion que se uso por error (en la lista de direcciones
de la app aparece como #N; la cuenta suele ser 0 y N es el indice menor).

No requiere instalar nada: solo Python 3.
"""

# ---------------------------------------------------------------------------
# Keccak-256 (el original, NO el SHA3 estandar de hashlib) en Python puro
# ---------------------------------------------------------------------------
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
_MASK = (1 << 64) - 1


def _rol(x, n):
    return ((x << n) | (x >> (64 - n))) & _MASK


def _keccak_f(st):
    for rnd in range(24):
        c = [st[x][0] ^ st[x][1] ^ st[x][2] ^ st[x][3] ^ st[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                st[x][y] ^= d[x]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(st[x][y], _ROT[x][y])
        for x in range(5):
            for y in range(5):
                st[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & _MASK & b[(x + 2) % 5][y])
        st[0][0] ^= _RC[rnd]
    return st


def keccak256(data: bytes) -> bytes:
    rate = 136
    st = [[0] * 5 for _ in range(5)]
    padded = bytearray(data) + b'\x01' + b'\x00' * ((-len(data) - 1) % rate)
    padded[-1] ^= 0x80
    for off in range(0, len(padded), rate):
        blk = padded[off:off + rate]
        for i in range(rate // 8):
            st[(i % 5)][(i // 5)] ^= int.from_bytes(blk[i * 8:(i + 1) * 8], 'little')
        _keccak_f(st)
    out = b''
    for i in range(4):
        out += st[i % 5][i // 5].to_bytes(8, 'little')
    return out


# ---------------------------------------------------------------------------
# Aritmetica del grupo ed25519
# ---------------------------------------------------------------------------
L = 2 ** 252 + 27742317777372353535851937790883648493


def sc_reduce32(b: bytes) -> int:
    return int.from_bytes(b, 'little') % L


def hex_to_scalar(h: str) -> int:
    return int.from_bytes(bytes.fromhex(h), 'little')


def scalar_to_hex(s: int) -> str:
    return s.to_bytes(32, 'little').hex()


# ---------------------------------------------------------------------------
def main():
    print(__doc__)
    print("=" * 70)
    print("  ¿HAS DESCONECTADO LA RED?  Si no, cierra esto (Ctrl+C) y hazlo.")
    print("=" * 70)
    input("\n  Pulsa Intro para continuar...\n")

    spend_hex = input("  secret spend key (64 hex): ").strip().lower()
    view_hex = input("  secret view key  (64 hex): ").strip().lower()
    major = int(input("  indice de cuenta   (normalmente 0): ").strip() or "0")
    minor = int(input("  indice de la subdireccion (el #N): ").strip())

    for name, h in (("spend", spend_hex), ("view", view_hex)):
        if len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
            print(f"\n  ERROR: la {name} key debe ser 64 caracteres hexadecimales.")
            return

    b = hex_to_scalar(spend_hex)   # clave de gasto de la cartera
    a = hex_to_scalar(view_hex)    # clave de vista de la cartera

    if major == 0 and minor == 0:
        print("\n  El indice 0,0 es la propia direccion principal: no hay nada que derivar.")
        return

    # m = Hs("SubAddr\0" || a || major_le32 || minor_le32)
    data = b"SubAddr\x00" + bytes.fromhex(view_hex) + \
        major.to_bytes(4, 'little') + minor.to_bytes(4, 'little')
    m = sc_reduce32(keccak256(data))

    d = (b + m) % L   # clave de gasto de la subdireccion

    print("\n" + "=" * 70)
    print("  CLAVE DE GASTO DERIVADA (subdireccion %d/%d)" % (major, minor))
    print("=" * 70)
    print("\n  " + scalar_to_hex(d) + "\n")
    print("  Guardala en un sitio seguro. Da control total sobre esos fondos.")
    print("=" * 70)
    print("""
  COMO USARLA PARA RECUPERAR EL DINERO

  Con monero-wallet-cli, crea una cartera a partir de claves:

      monero-wallet-cli --generate-from-keys cartera-recuperacion

  Te pedira tres cosas:

      Standard address : 423P2YRSNPujeUFUxVjL6TFaW87iQmgdRVSfcKEWUCLH723
                         fDcyXW7DEiEzDRTYDPcJDKN9KsVkPLZ7D8rzwhZqN9SJhRXq
      Spend key        : la clave derivada de arriba
      View key         : la MISMA clave de vista que se puso en BTCPay

  Luego, dentro de la cartera:

      restore_height <altura>     (usa una anterior al pago)
      refresh
      balance
      transfer <tu_direccion_48VdLk...> <cantidad>

  Con eso los fondos vuelven a tu cartera principal.
""")


if __name__ == '__main__':
    main()

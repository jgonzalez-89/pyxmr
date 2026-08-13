# pyxmr

Deriva la **clave de gasto de una subdirección de Monero** a partir de las claves
privadas de la cartera.

Sirve para recuperar fondos que han acabado en direcciones que la cartera original
no reconoce, cuando por error se ha usado una **subdirección** donde se esperaba la
**dirección principal**.

Sin dependencias: solo Python 3. Pensado para ejecutarse **sin conexión a internet**.

---

## El problema que resuelve

Las direcciones de Monero tienen dos formatos, y se distinguen por el primer carácter:

| Empieza por | Qué es | Uso |
|---|---|---|
| `4…` | **Dirección principal** | La identidad de la cartera |
| `8…` | **Subdirección** | Una dirección de recibir, derivada de la principal |

Muchos programas —pasarelas de pago, TPV, integraciones— piden la **dirección
principal** para poder generar por su cuenta subdirecciones nuevas en cada cobro.

Si en ese campo se pega una **subdirección** por equivocación, puede ocurrir esto:

1. El programa toma las claves públicas de la subdirección y las trata como si
   fueran las de una cartera principal.
2. A partir de esa base **construye subdirecciones nuevas** y las usa para cobrar.
3. Los pagos llegan correctamente a la cadena de bloques… pero a direcciones que
   **la cartera original no busca**, porque no las considera suyas.

El dinero no se pierde ni se destruye: queda en direcciones cuya clave de gasto
nadie tiene *directamente*, pero que **sí se puede derivar** si se conocen las
claves privadas de la cartera y el índice de la subdirección implicada. Eso es lo
que hace este script.

---

## Cómo funciona (para que puedas auditarlo)

En Monero, la subdirección de índice `(major, minor)` de una cartera con clave
privada de gasto `b` y clave privada de vista `a` se deriva así:

```
m = Hs( "SubAddr\0" || a || major_le32 || minor_le32 )
D = B + m·G                 (clave pública de gasto de la subdirección)
```

donde `Hs` es Keccak-256 reducido módulo `L`, el orden del grupo ed25519.

La clave **privada** correspondiente a `D` es simplemente:

```
d = (b + m)  mod  L
```

Eso es todo lo que calcula el script: **una función hash y una suma modular**.
El resto del fichero (unas 120 líneas) es la implementación de Keccak-256 en
Python puro, para no depender de librerías externas.

> Nota: Monero usa **Keccak-256 original**, no el SHA3-256 estandarizado.
> `hashlib.sha3_256` daría un resultado distinto y la clave sería incorrecta.

Referencia: [Monero — Subaddresses](https://www.getmonero.org/resources/moneropedia/subaddress.html)

---

## Auditar el script en dos minutos

Antes de meter ninguna clave privada en un programa descargado de internet,
compruébalo. Es lo prudente y no cuesta nada:

**1. No tiene acceso a red.** No importa ningún módulo de red ni ejecuta procesos:

```bash
grep -nE "socket|urllib|request|http|subprocess|os\.system|open\(" py_xmr.py
```

No debe devolver **ninguna** línea.

**2. No escribe en disco.** La clave solo se imprime en pantalla; no se guarda.

**3. El cálculo son cinco líneas.** Busca `m = sc_reduce32` y `d = (b + m) % L`.
Todo lo demás es Keccak y la interfaz de texto.

**4. Verifica el Keccak** contra los valores conocidos:

```bash
python3 -c "
exec(open('py_xmr.py').read().split('def main')[0])
print(keccak256(b'').hex())
print(keccak256(b'abc').hex())
"
```

Debe imprimir exactamente:

```
c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470
4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45
```

Si coinciden, la implementación de Keccak es correcta.

---

## Qué necesitas

- **Python 3** (en macOS y Linux ya viene instalado; en Windows, desde
  [python.org](https://www.python.org/downloads/) marcando *Add to PATH*).
- La **clave privada de gasto** y la **clave privada de vista** de tu cartera.
- El **índice** de la subdirección que se usó por error.

### Obtener las claves

Con la cartera abierta en `monero-wallet-cli`:

```
spendkey        →  secret spend key   (64 caracteres hexadecimales)
viewkey         →  secret view key    (64 caracteres hexadecimales)
```

En las carteras gráficas suelen estar en *Configuración → Semilla y claves*.

### Obtener el índice

En la lista de direcciones de tu cartera, localiza la subdirección que se usó por
error. A su izquierda aparece un número: `#0`, `#1`, `#2`… Ese es el **índice
menor** (`minor`). El **índice de cuenta** (`major`) suele ser `0`.

---

## Uso

```bash
# 1. Descarga el script CON conexión
curl -O https://raw.githubusercontent.com/jgonzalez-89/pyxmr/main/py_xmr.py

# 2. DESCONECTA LA RED  (wifi y cable)

# 3. Ejecútalo
python3 py_xmr.py
```

Te pedirá los cuatro datos y te devolverá la clave de gasto derivada.

---

## Recuperar los fondos

Con la clave derivada, crea una cartera a partir de claves:

```bash
monero-wallet-cli --generate-from-keys cartera-recuperacion
```

Te pedirá tres cosas:

| Campo | Qué poner |
|---|---|
| **Standard address** | La dirección principal que construyó el programa por error (empieza por `4…`) |
| **Spend key** | La clave derivada por este script |
| **View key** | La misma clave de vista que se configuró en el programa |

Y dentro de la cartera:

```
restore_height <altura>     # una altura anterior al primer pago
refresh
balance
transfer <tu_direccion_principal> <cantidad>
```

Con eso los fondos vuelven a tu cartera de siempre.

---

## Seguridad

- **Ejecútalo solo en tu ordenador.** Nunca en un servidor, ni en el equipo de
  otra persona, ni en una máquina compartida.
- **Desconecta la red** antes de teclear las claves.
- **La clave que imprime da control total sobre esos fondos.** Trátala igual que
  tu frase semilla: no la mandes por correo, chat ni la subas a ningún sitio.
- **No compartas tu clave de gasto con nadie.** Ninguna persona ni servicio
  legítimo te la pedirá jamás.
- **Borra el script y cierra la terminal** cuando termines.

---

## Cómo evitar que vuelva a pasar

Cuando un servicio te pida la dirección de tu cartera Monero para recibir pagos,
comprueba que empieza por **`4`**. Si empieza por `8`, es una dirección de recibir
y no sirve para ese campo.

---

## Licencia

MIT. Sin garantía de ningún tipo: revisa el código antes de usarlo con fondos reales.

/-!
# Lean Kernel Challenge problem `sha256` — SPEC (trusted, locked)

The SHA-256 hash chain: starting from the all-zero 256-bit digest, apply full
SHA-256 (of the 32-byte previous digest, one padded block) `n` times
(`sha256Spec : Nat → Nat`); the result is the final digest as a natural number
(big-endian). Constants and structure follow FIPS 180-4 exactly; the reference
values below were cross-checked against an independent implementation.

The spec is deliberately naive: one 32-bit word per `Nat`, a `List Nat` message
schedule grown one word at a time, and one structure update per round, so every
word operation is a separate kernel reduction step. The chain is inherently
sequential — there is no logarithmic shortcut — so submissions win on kernel-fu:
cheaper word representations (e.g. packing the state into a single `Nat` and
exploiting the kernel's GMP-accelerated big-`Nat` bitwise ops), fused round
functions, or a cheaper but provably equal schedule.

Check: `sha256Spec 0 = 0`, and
`sha256Spec 1 = 0x66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925`
(the SHA-256 digest of 32 zero bytes).
-/

/-- All word values are kept `< 2^32` by masking with this constant. -/
def w32 : Nat := 0xFFFFFFFF

def add32 (a b : Nat) : Nat := (a + b) &&& w32

/-- Right-rotation of a 32-bit word. -/
def rotr32 (x n : Nat) : Nat := ((x >>> n) ||| (x <<< (32 - n))) &&& w32

/-- The eight 32-bit working variables of SHA-256 (FIPS 180-4 a–h). -/
structure Digest where
  a : Nat
  b : Nat
  c : Nat
  d : Nat
  e : Nat
  f : Nat
  g : Nat
  h : Nat

/-- Initial hash value H⁽⁰⁾ (FIPS 180-4 §5.3.3). -/
def iv : Digest :=
  ⟨0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
   0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19⟩

/-- Round constants K (FIPS 180-4 §4.2.2). -/
def K : List Nat := [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]

def smallSigma0 (x : Nat) : Nat := (rotr32 x 7) ^^^ (rotr32 x 18) ^^^ (x >>> 3)
def smallSigma1 (x : Nat) : Nat := (rotr32 x 17) ^^^ (rotr32 x 19) ^^^ (x >>> 10)
def bigSigma0 (x : Nat) : Nat := (rotr32 x 2) ^^^ (rotr32 x 13) ^^^ (rotr32 x 22)
def bigSigma1 (x : Nat) : Nat := (rotr32 x 6) ^^^ (rotr32 x 11) ^^^ (rotr32 x 25)

/-- Ch(x,y,z); `x ^^^ w32` is 32-bit complement (all words stay `< 2^32`). -/
def ch (x y z : Nat) : Nat := (x &&& y) ^^^ ((x ^^^ w32) &&& z)
def maj (x y z : Nat) : Nat := (x &&& y) ^^^ (x &&& z) ^^^ (y &&& z)

/-- Extend the message schedule by `k` words: each new word is
`σ₁(w[t-2]) + w[t-7] + σ₀(w[t-15]) + w[t-16]` (window indices 14, 9, 1, 0). -/
def extendW : Nat → List Nat → List Nat
  | 0, ws => ws
  | k + 1, ws =>
    let win := ws.drop (ws.length - 16)
    extendW k (ws ++ [add32 (add32 (smallSigma1 (win.getD 14 0)) (win.getD 9 0))
                            (add32 (smallSigma0 (win.getD 1 0)) (win.getD 0 0))])

/-- One SHA-256 round (FIPS 180-4 §6.2.2 step 3). -/
def round (s : Digest) (k w : Nat) : Digest :=
  let t1 := add32 s.h (add32 (bigSigma1 s.e) (add32 (ch s.e s.f s.g) (add32 k w)))
  let t2 := add32 (bigSigma0 s.a) (maj s.a s.b s.c)
  ⟨add32 t1 t2, s.a, s.b, s.c, add32 s.d t1, s.e, s.f, s.g⟩

def rounds : List (Nat × Nat) → Digest → Digest
  | [], s => s
  | (k, w) :: rest, s => rounds rest (round s k w)

/-- Compress one 16-word block into the chaining state. -/
def compress (s : Digest) (block : List Nat) : Digest :=
  let f := rounds (K.zip (extendW 48 block)) s
  ⟨add32 s.a f.a, add32 s.b f.b, add32 s.c f.c, add32 s.d f.d,
   add32 s.e f.e, add32 s.f f.f, add32 s.g f.g, add32 s.h f.h⟩

/-- SHA-256 of a 32-byte message given as 8 big-endian words. The padded
message is exactly one block: the 8 words, the leading `1` bit (`0x80000000`),
five zero words, and the 64-bit bit-length 256 (`0, 256`). -/
def sha256step (d : Digest) : Digest :=
  compress iv [d.a, d.b, d.c, d.d, d.e, d.f, d.g, d.h,
               0x80000000, 0, 0, 0, 0, 0, 0, 256]

def iterSha : Nat → Digest → Digest
  | 0, d => d
  | t + 1, d => iterSha t (sha256step d)

/-- The digest as a big-endian natural number. -/
def encodeDigest (d : Digest) : Nat :=
  [d.a, d.b, d.c, d.d, d.e, d.f, d.g, d.h].foldl
    (fun acc w => acc * 4294967296 + w) 0

/-- Parametric spec: the SHA-256 hash chain after `n` steps, started from the
all-zero digest. -/
def sha256Spec (n : Nat) : Nat := encodeDigest (iterSha n ⟨0, 0, 0, 0, 0, 0, 0, 0⟩)

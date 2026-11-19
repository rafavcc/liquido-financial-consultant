/** Decimal em string → centavos (BigInt), arredondando half-even a 2 casas. Sem float. */
function toCents(s: string): bigint {
  const m = /^(-?)(\d*)(?:\.(\d*))?$/.exec(s.trim());
  if (!m) throw new Error(`Valor monetário inválido: ${s}`);
  const [, sign, int, frac = ""] = m;
  const padded = frac.padEnd(3, "0");
  let cents = BigInt((int || "0") + padded.slice(0, 2));
  const rest = padded.slice(2);
  const first = Number(rest[0]);
  const tail = /[1-9]/.test(rest.slice(1));
  if (first > 5 || (first === 5 && (tail || cents % 2n === 1n))) cents += 1n;
  return sign ? -cents : cents;
}

/** a − b em dinheiro, exato; devolve string com 2 casas. */
export function subtractMoney(a: string, b: string): string {
  const d = toCents(a) - toCents(b);
  const neg = d < 0n;
  const abs = (neg ? -d : d).toString().padStart(3, "0");
  return `${neg ? "-" : ""}${abs.slice(0, -2)}.${abs.slice(-2)}`;
}

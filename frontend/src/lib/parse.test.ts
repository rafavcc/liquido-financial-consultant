import { parseBRL } from "./parse";

test.each([
  ["50.000,00", "50000.00"],
  ["50000", "50000"],
  ["50.000", "50000"],
  ["1.234,5", "1234.5"],
  ["R$ 2.500,75", "2500.75"],
  ["abc", null],
  ["0", "0"],
  ["", null],
  ["1,2,3", null],
])("parseBRL(%s)", (i, o) => expect(parseBRL(i)).toBe(o));

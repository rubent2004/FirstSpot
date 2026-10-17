import { readFileSync } from "node:fs";
import { resolve as resolvePath } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * WCAG 2.2 AA contrast for the text/surface token pairs, in BOTH themes.
 * Measured from the real style.css, so a token edit that breaks a pair fails
 * here instead of in front of an operator.
 */
const CSS = readFileSync(resolvePath(process.cwd(), "src/style.css"), "utf8");

type Rgba = { r: number; g: number; b: number; a: number };

function blockAfter(selectorStart: string): string {
  const start = CSS.indexOf(selectorStart);
  if (start < 0) throw new Error(`block not found: ${selectorStart}`);
  const open = CSS.indexOf("{", start);
  const close = CSS.indexOf("\n}", open);
  return CSS.slice(open + 1, close);
}

function tokensOf(block: string): Map<string, string> {
  const map = new Map<string, string>();
  for (const m of block.matchAll(/(--[\w-]+):\s*([^;]+);/g)) map.set(m[1], m[2].trim());
  return map;
}

const THEMES = {
  dark: tokensOf(blockAfter(":root,\n.theme-dark")),
  light: tokensOf(blockAfter("html:not(.dark),\n.theme-light")),
} as const;
type ThemeName = keyof typeof THEMES;

function resolve(theme: ThemeName, name: string): string {
  let value = THEMES[theme].get(name);
  if (value === undefined) throw new Error(`${theme}: missing ${name}`);
  const ref = /^var\((--[\w-]+)\)$/.exec(value);
  if (ref) value = resolve(theme, ref[1]);
  return value;
}

function parse(value: string): Rgba {
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
  }
  const rgba = /^rgba?\(([^)]+)\)$/.exec(value);
  if (rgba) {
    const [r, g, b, a = "1"] = rgba[1].split(",").map((s) => s.trim());
    return { r: +r, g: +g, b: +b, a: +a };
  }
  throw new Error(`unsupported colour: ${value}`);
}

function over(top: Rgba, base: Rgba): Rgba {
  const mix = (f: number, b: number) => Math.round(f * top.a + b * (1 - top.a));
  return { r: mix(top.r, base.r), g: mix(top.g, base.g), b: mix(top.b, base.b), a: 1 };
}

function luminance({ r, g, b }: Rgba): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function ratio(fg: Rgba, bg: Rgba): number {
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

function colour(theme: ThemeName, token: string, under?: string): Rgba {
  const c = parse(resolve(theme, token));
  return c.a < 1 && under ? over(c, colour(theme, under)) : c;
}

const SURFACES = [
  "--eoc-bg-panel",
  "--eoc-bg-card",
  "--eoc-bg-sunken",
  "--eoc-bg-header",
  "--eoc-bg-statusbar",
  "--eoc-bg-hover",
  "--eoc-bg-selected",
];

const TEXT_ON_SURFACES = [
  "--eoc-text-primary",
  "--eoc-text-secondary",
  "--eoc-text-muted",
  "--eoc-text-label",
  "--eoc-accent-text",
];

/** Class/semantic hues are used as text on a tinted background over a panel. */
const CLASS_TEXT: Array<[string, string]> = [
  ["--eoc-alert-roja", "--eoc-critical-bg"],
  ["--eoc-alert-naranja", "--eoc-alert-naranja-bg"],
  ["--eoc-alert-amarilla", "--eoc-warning-bg"],
  ["--eoc-alert-verde", "--eoc-success-bg"],
  ["--eoc-critical", "--eoc-critical-bg"],
  ["--eoc-info", "--eoc-info-bg"],
];

describe.each(Object.keys(THEMES) as ThemeName[])("contrast (%s theme)", (theme) => {
  for (const text of TEXT_ON_SURFACES) {
    for (const surface of SURFACES) {
      it(`${text} on ${surface} is at least 4.5:1`, () => {
        const value = ratio(colour(theme, text), colour(theme, surface));
        expect(value).toBeGreaterThanOrEqual(4.5);
      });
    }
  }

  for (const [fg, bg] of CLASS_TEXT) {
    it(`${fg} on ${bg} over the panel is at least 4.5:1`, () => {
      const back = colour(theme, bg, "--eoc-bg-panel");
      expect(ratio(colour(theme, fg), back)).toBeGreaterThanOrEqual(4.5);
    });
  }

  it("on-accent text on the accent fill is at least 4.5:1", () => {
    expect(
      ratio(colour(theme, "--eoc-on-accent"), colour(theme, "--eoc-accent")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("the focus ring is at least 3:1 against the panel and the card", () => {
    for (const surface of ["--eoc-bg-panel", "--eoc-bg-card"]) {
      expect(
        ratio(colour(theme, "--eoc-border-focus"), colour(theme, surface)),
      ).toBeGreaterThanOrEqual(3);
    }
  });
});

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";

/**
 * Readers for the exported files, so each one is opened and checked the way a
 * person would open it, not trusted from the code that wrote it.
 */

// ---- xlsx (a zip of XML parts) ----

/** Minimal zip reader: central directory, stored or deflated entries. Enough for an xlsx. */
export function unzip(buffer: Buffer): Map<string, Buffer> {
  const entries = new Map<string, Buffer>();
  const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (eocd < 0) throw new Error("not a zip file: no end of central directory");
  const count = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);
  for (let i = 0; i < count; i++) {
    if (buffer.readUInt32LE(offset) !== 0x02014b50) throw new Error("bad central directory entry");
    const method = buffer.readUInt16LE(offset + 10);
    const compressedSize = buffer.readUInt32LE(offset + 20);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const localOffset = buffer.readUInt32LE(offset + 42);
    const name = buffer.toString("utf8", offset + 46, offset + 46 + nameLength);
    const localNameLength = buffer.readUInt16LE(localOffset + 26);
    const localExtraLength = buffer.readUInt16LE(localOffset + 28);
    const start = localOffset + 30 + localNameLength + localExtraLength;
    const data = buffer.subarray(start, start + compressedSize);
    entries.set(name, method === 8 ? inflateRawSync(data) : Buffer.from(data));
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

const decodeXml = (text: string): string =>
  text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n: string) => String.fromCodePoint(Number(n)))
    .replace(/&amp;/g, "&");

export type Cell = string | number | null;

export interface Workbook {
  /** Sheet name to rows of cells (missing cells are null, in column order). */
  sheets: Map<string, Cell[][]>;
}

function columnIndex(ref: string): number {
  const letters = /^[A-Z]+/.exec(ref)?.[0] ?? "A";
  let n = 0;
  for (const ch of letters) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n - 1;
}

export function readXlsx(file: string): Workbook {
  const parts = unzip(readFileSync(file));
  const text = (name: string) => parts.get(name)?.toString("utf8") ?? "";

  const shared: string[] = [];
  for (const si of text("xl/sharedStrings.xml").matchAll(/<si>([\s\S]*?)<\/si>/g)) {
    const runs = [...si[1].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((m) => decodeXml(m[1]));
    shared.push(runs.join(""));
  }

  const rels = new Map<string, string>();
  for (const rel of text("xl/_rels/workbook.xml.rels").matchAll(/<Relationship\b[^>]*>/g)) {
    const id = /Id="([^"]+)"/.exec(rel[0])?.[1];
    const target = /Target="([^"]+)"/.exec(rel[0])?.[1];
    if (id && target) rels.set(id, target.replace(/^\/?(xl\/)?/, "xl/"));
  }

  const sheets = new Map<string, Cell[][]>();
  for (const sheet of text("xl/workbook.xml").matchAll(/<sheet\b[^>]*>/g)) {
    const name = decodeXml(/name="([^"]+)"/.exec(sheet[0])?.[1] ?? "");
    const rid = /r:id="([^"]+)"/.exec(sheet[0])?.[1] ?? "";
    const xml = text(rels.get(rid) ?? "");
    const rows: Cell[][] = [];
    for (const row of xml.matchAll(/<row\b[^>]*?(?:\/>|>([\s\S]*?)<\/row>)/g)) {
      const cells: Cell[] = [];
      for (const c of (row[1] ?? "").matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
        const attrs = c[1];
        const body = c[2] ?? "";
        const ref = /r="([A-Z]+\d+)"/.exec(attrs)?.[1];
        const type = /t="([^"]+)"/.exec(attrs)?.[1];
        const index = ref ? columnIndex(ref) : cells.length;
        let value: Cell = null;
        const v = /<v>([\s\S]*?)<\/v>/.exec(body)?.[1];
        if (type === "s" && v !== undefined) value = shared[Number(v)] ?? null;
        else if (type === "inlineStr") {
          value = [...body.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((m) => decodeXml(m[1])).join("");
        } else if (type === "str" || type === "b") value = v === undefined ? null : decodeXml(v);
        else if (v !== undefined) value = Number(v);
        while (cells.length < index) cells.push(null);
        cells[index] = value;
      }
      rows.push(cells);
    }
    sheets.set(name, rows);
  }
  return { sheets };
}

// ---- csv ----

/** RFC 4180 parser (quoted fields, doubled quotes, CRLF). Keeps the BOM out of the cells. */
export function parseCsv(text: string): string[][] {
  const body = text.startsWith("﻿") ? text.slice(1) : text;
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < body.length; i++) {
    const ch = body[i];
    if (quoted) {
      if (ch === '"' && body[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
      continue;
    }
    if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\r" && body[i + 1] === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      i++;
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += ch;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

// ---- pdf ----

/**
 * The text and page count of a PDF, read with poppler (`pdftotext`, `pdfinfo`),
 * the same text a reader gets when copying from the file. pdf.js was tried and
 * drops digits set with tabular-nums, so it would report false failures.
 */
export function readPdfText(file: string): { pages: number; text: string } {
  const run = (tool: string, args: string[]): string => {
    try {
      return execFileSync(tool, args, { encoding: "utf8" });
    } catch (error) {
      throw new Error(`${tool} failed (install poppler-utils to read PDFs): ${String(error)}`);
    }
  };
  const info = run("pdfinfo", [file]);
  const pages = Number(/^Pages:\s+(\d+)/m.exec(info)?.[1] ?? 0);
  return { pages, text: run("pdftotext", [file, "-"]) };
}

/** Collapse whitespace so a line wrapped by the PDF layout still matches. */
export const squash = (text: string): string => text.replace(/\s+/g, " ").trim();

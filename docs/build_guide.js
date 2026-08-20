/*
 * Builds the Plover User Guide (.docx) from the markdown chapters in
 * docs/chapters/ and the figures in docs/images/.
 *
 *   node docs/build_guide.js
 *
 * Requires the "docx" npm package. If it is installed globally, run with:
 *   NODE_PATH="$(npm root -g)" node docs/build_guide.js
 */

const fs = require("fs");
const path = require("path");

const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel,
  ImageRun, LevelFormat, Packer, PageBreak, PageNumber, Paragraph,
  ShadingType, Table, TableCell, TableRow, TextRun, TableOfContents,
  ExternalHyperlink, WidthType, VerticalAlign,
} = require("docx");

const REPO = path.resolve(__dirname, "..");
const IMAGES = path.join(REPO, "docs", "images");
const CHAPTERS = path.join(REPO, "docs", "chapters");

const ORDER = ["intro", "install", "data", "dialog", "workflows",
               "outputs", "processing", "trouble", "appendix"];

// ---------------------------------------------------------------- constants

const CONTENT_W = 9360;        // 6.5" in DXA
const MAX_IMG_PX = 610;        // fits 6.5" at 96 dpi with a little slack
const ACCENT = "C2410C";       // plover orange, darkened for print
const INK = "1F2933";
const MUTED = "5B6670";
const RULE = "D6DCE2";
const CODE_BG = "F5F6F7";

let LIST_INSTANCE = 0;   // a fresh instance per ordered list so numbering restarts

const VERSION = (fs.readFileSync(
  path.join(REPO, "tsp_route_generator", "metadata.txt"), "utf8")
  .match(/^version=(.+)$/m) || [, "?"])[1].trim();

// ------------------------------------------------------------ png dimensions

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// --------------------------------------------------------- inline formatting

/** Split markdown inline markup into docx runs. Recurses so that nested
 *  markup such as **`code`** renders as bold code rather than literal ticks. */
function runs(text, base = {}) {
  const out = [];
  // order matters: code first so markup inside a code span is left alone
  const re = /(`[^`]+`)|(\*\*[\s\S]+?\*\*)|(\[[^\]]+\]\([^)]+\))|(<https?:\/\/[^>]+>)|(\*[^*\n]+\*)/g;
  let last = 0, m;
  const plain = (s) => {
    if (s) out.push(new TextRun({ text: s, ...base }));
  };
  while ((m = re.exec(text)) !== null) {
    plain(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      out.push(new TextRun({
        text: tok.slice(1, -1), font: "Consolas", size: 19,
        color: "9A3412", shading: { type: ShadingType.CLEAR, fill: CODE_BG },
        ...(base.bold ? { bold: true } : {}),
        ...(base.italics ? { italics: true } : {}),
      }));
    } else if (tok.startsWith("**")) {
      out.push(...runs(tok.slice(2, -2), { ...base, bold: true }));
    } else if (tok.startsWith("[")) {
      const mm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      out.push(new ExternalHyperlink({
        link: mm[2],
        children: [new TextRun({
          text: mm[1], ...base, color: "1D4ED8", underline: {},
        })],
      }));
    } else if (tok.startsWith("<http")) {
      const url = tok.slice(1, -1);
      out.push(new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text: url, ...base, color: "1D4ED8", underline: {} })],
      }));
    } else {
      out.push(...runs(tok.slice(1, -1), { ...base, italics: true }));
    }
    last = m.index + tok.length;
  }
  plain(text.slice(last));
  return out.length ? out : [new TextRun({ text: "", ...base })];
}

// ------------------------------------------------------------------ builders

const body = (text, opts = {}) => new Paragraph({
  children: runs(text),
  spacing: { after: 130, line: 288 },
  ...opts,
});

function figure(slug, caption, num) {
  const file = path.join(IMAGES, `${slug}.png`);
  if (!fs.existsSync(file)) {
    console.warn(`  ! missing figure: ${slug}`);
    return [];
  }
  const { w, h } = pngSize(file);
  const scale = Math.min(1, MAX_IMG_PX / w);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 60 },
      children: [new ImageRun({
        data: fs.readFileSync(file), type: "png",
        transformation: { width: Math.round(w * scale), height: Math.round(h * scale) },
      })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 220 },
      children: [
        new TextRun({ text: `Figure ${num}. `, bold: true, size: 18, color: MUTED }),
        ...runs(caption, { size: 18, color: MUTED, italics: true }),
      ],
    }),
  ];
}

function codeBlock(lines) {
  return lines.map((ln, i) => new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: CODE_BG },
    spacing: { before: i === 0 ? 120 : 0, after: i === lines.length - 1 ? 160 : 0 },
    indent: { left: 220, right: 220 },
    border: {
      left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 10 },
    },
    children: [new TextRun({
      text: ln.length ? ln : " ", font: "Consolas", size: 18, color: "23303B",
    })],
  }));
}

function quote(lines) {
  return lines.map((ln, i) => new Paragraph({
    children: runs(ln, { size: 20, color: "334155" }),
    spacing: { before: i === 0 ? 130 : 0, after: i === lines.length - 1 ? 170 : 40, line: 276 },
    indent: { left: 260, right: 160 },
    shading: { type: ShadingType.CLEAR, fill: "FBF7F2" },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 12 } },
  }));
}

function makeTable(rows) {
  // Some source tables have a deliberately blank header row; drop it rather
  // than rendering an empty shaded band.
  let hasHeader = true;
  if (rows.length > 1 && rows[0].every((c) => !c.trim())) {
    rows = rows.slice(1);
    hasHeader = false;
  }
  const cols = Math.max(...rows.map((r) => r.length));
  // give the first column a little extra room when there are few columns
  const widths = [];
  if (cols === 2) { widths.push(Math.round(CONTENT_W * 0.36)); widths.push(CONTENT_W - Math.round(CONTENT_W * 0.36)); }
  else if (cols === 3) { widths.push(Math.round(CONTENT_W * 0.28), Math.round(CONTENT_W * 0.22)); widths.push(CONTENT_W - widths[0] - widths[1]); }
  else {
    const base = Math.floor(CONTENT_W / cols);
    for (let i = 0; i < cols - 1; i++) widths.push(base);
    widths.push(CONTENT_W - base * (cols - 1));
  }

  const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
  const trs = rows.map((cells, ri) => new TableRow({
    tableHeader: hasHeader && ri === 0,
    children: Array.from({ length: cols }, (_, ci) => new TableCell({
      width: { size: widths[ci], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: (hasHeader && ri === 0) ? "EFF3F6" : "FFFFFF" },
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      verticalAlign: VerticalAlign.CENTER,
      borders: { top: border, bottom: border, left: border, right: border },
      children: [new Paragraph({
        spacing: { after: 0, line: 264 },
        children: runs(cells[ci] || "", { size: 19, ...((hasHeader && ri === 0) ? { bold: true } : {}) }),
      })],
    })),
  }));

  return new Table({
    rows: trs,
    columnWidths: widths,
    width: { size: CONTENT_W, type: WidthType.DXA },
  });
}

// ----------------------------------------------------------------- md parser

function parseMarkdown(md, chapterNum, state) {
  const out = [];
  const lines = md.split(/\r?\n/);
  let i = 0;

  const flushList = (items, ordered) => {
    const instance = ordered ? (LIST_INSTANCE += 1) : 0;
    items.forEach((txt) => out.push(new Paragraph({
      children: runs(txt),
      numbering: { reference: ordered ? "num" : "bul", level: 0, instance },
      spacing: { after: 70, line: 282 },
    })));
  };

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) { i++; continue; }

    // fenced code
    if (/^```/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      out.push(...codeBlock(buf));
      continue;
    }

    // figure placeholder
    const fig = /^\[\[FIGURE:\s*([a-z0-9-]+)\s*\|\s*([\s\S]*?)\]\]$/.exec(line.trim());
    if (fig) {
      state.fig += 1;
      out.push(...figure(fig[1], fig[2].trim(), `${chapterNum}.${state.fig}`));
      i++;
      continue;
    }

    // headings
    const h = /^(#{2,5})\s+(.*)$/.exec(line);
    if (h) {
      const depth = h[1].length;             // 2 = chapter, 3 = section, ...
      const text = h[2].trim();
      if (depth === 2) {
        out.push(new Paragraph({
          heading: HeadingLevel.HEADING_1,
          pageBreakBefore: true,
          spacing: { before: 40, after: 260 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 14, color: ACCENT, space: 10 } },
          children: runs(text, { bold: true, size: 40, color: INK }),
        }));
      } else {
        const sizes = { 3: 27, 4: 23, 5: 21 };
        const levels = { 3: HeadingLevel.HEADING_2, 4: HeadingLevel.HEADING_3, 5: HeadingLevel.HEADING_4 };
        out.push(new Paragraph({
          heading: levels[depth],
          spacing: { before: depth === 3 ? 300 : 220, after: 110 },
          keepNext: true,
          children: runs(text, {
            bold: true, size: sizes[depth], color: depth === 3 ? ACCENT : INK,
          }),
        }));
      }
      i++;
      continue;
    }

    // horizontal rule
    if (/^---+$/.test(line.trim())) {
      out.push(new Paragraph({
        spacing: { before: 120, after: 120 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: RULE, space: 6 } },
        children: [new TextRun("")],
      }));
      i++;
      continue;
    }

    // table
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const split = (r) => r.trim().replace(/^\|/, "").replace(/\|$/, "")
        .split("|").map((c) => c.trim());
      const rows = [split(lines[i])];
      i += 2;
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(split(lines[i++]));
      out.push(makeTable(rows));
      out.push(new Paragraph({ spacing: { after: 200 }, children: [new TextRun("")] }));
      continue;
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ""));
      out.push(...quote(buf.filter((s) => s.trim().length)));
      continue;
    }

    // lists
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+\.\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const items = [];
      while (i < lines.length) {
        const b = /^\s*[-*]\s+(.*)$/.exec(lines[i]);
        const n = /^\s*\d+\.\s+(.*)$/.exec(lines[i]);
        if (ordered && n) items.push(n[1]);
        else if (!ordered && b) items.push(b[1]);
        else if (lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length) {
          items[items.length - 1] += " " + lines[i].trim();     // continuation
        } else break;
        i++;
      }
      flushList(items, ordered);
      continue;
    }

    // paragraph
    const buf = [line];
    i++;
    while (i < lines.length && lines[i].trim()
           && !/^(#{2,5}\s|```|>\s?|\s*[-*]\s|\s*\d+\.\s|\s*\|)/.test(lines[i])
           && !/^\[\[FIGURE:/.test(lines[i].trim())
           && !/^---+$/.test(lines[i].trim())) {
      buf.push(lines[i++]);
    }
    out.push(body(buf.join(" ")));
  }

  return out;
}

// ------------------------------------------------------------------ title page

function titlePage() {
  const icon = path.join(REPO, "tsp_route_generator", "icon.png");
  const kids = [];

  kids.push(new Paragraph({ spacing: { before: 1900 }, children: [new TextRun("")] }));

  if (fs.existsSync(icon)) {
    const { w, h } = pngSize(icon);
    const s = 132 / w;
    kids.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
      children: [new ImageRun({
        data: fs.readFileSync(icon), type: "png",
        transformation: { width: Math.round(w * s), height: Math.round(h * s) },
      })],
    }));
  }

  kids.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 60 },
    children: [new TextRun({ text: "Plover", bold: true, size: 76, color: INK })],
  }));
  kids.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 40 },
    children: [new TextRun({ text: "User Guide", size: 44, color: ACCENT })],
  }));
  kids.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 420 },
    children: [new TextRun({
      text: "Boundary-aware Travelling Salesperson routing for QGIS",
      size: 22, color: MUTED, italics: true,
    })],
  }));

  const meta = [
    ["Plugin version", VERSION],
    ["Plugin folder", "tsp_route_generator"],
    ["QGIS versions", "3.22 and newer (Qt5 and Qt6)"],
    ["Licence", "MIT"],
    ["Author", "Zachary Komarnisky"],
    ["Repository", "github.com/Dozer3530/Plover"],
    ["Plugin page", "plugins.qgis.org/plugins/tsp_route_generator"],
  ];
  const w0 = 3000, w1 = 4400;
  const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  kids.push(new Table({
    columnWidths: [w0, w1],
    width: { size: w0 + w1, type: WidthType.DXA },
    alignment: AlignmentType.CENTER,
    rows: meta.map(([k, v]) => new TableRow({
      children: [
        new TableCell({
          width: { size: w0, type: WidthType.DXA },
          borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
          margins: { top: 46, bottom: 46, left: 60, right: 60 },
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            spacing: { after: 0 },
            children: [new TextRun({ text: k, size: 19, color: MUTED })],
          })],
        }),
        new TableCell({
          width: { size: w1, type: WidthType.DXA },
          borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
          margins: { top: 46, bottom: 46, left: 60, right: 60 },
          children: [new Paragraph({
            spacing: { after: 0 },
            children: [new TextRun({ text: v, size: 19, bold: true, color: INK })],
          })],
        }),
      ],
    })),
  }));

  kids.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 700 },
    children: [new TextRun({
      text: "This document is generated from the plugin source. "
          + "Rebuild it with docs/build_guide.js after changing the plugin.",
      size: 16, color: MUTED, italics: true,
    })],
  }));

  // ---- contents ----
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  kids.push(new Paragraph({
    spacing: { after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 14, color: ACCENT, space: 10 } },
    children: [new TextRun({ text: "Contents", bold: true, size: 40, color: INK })],
  }));
  kids.push(new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: "If the list below is empty or out of date, click it and press F9 "
          + "(or right-click and choose Update Field) to rebuild it.",
      size: 18, color: MUTED, italics: true,
    })],
  }));
  kids.push(new TableOfContents("Contents", {
    hyperlink: true, headingStyleRange: "1-3",
  }));

  // ---- how to use ----
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  kids.push(new Paragraph({
    spacing: { after: 220 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 14, color: ACCENT, space: 10 } },
    children: [new TextRun({ text: "How to use this guide", bold: true, size: 40, color: INK })],
  }));
  [
    "This guide covers Plover end to end: what it is, how to install it, how to prepare data for it, every control in its dialog, step-by-step workflows for the jobs you will actually do, how to get results into the field, how to automate it, and what to do when something goes wrong.",
    "You do not need to read it front to back. Use it like this:",
  ].forEach((t) => kids.push(body(t)));

  const guideRows = [
    ["If you are...", "Start at"],
    ["Installing Plover for the first time", "Chapter 2"],
    ["New to the plugin and want to route a field today", "Chapter 1, then Workflow 5.1"],
    ["Getting an error or an unexpected route", "Chapter 8, Part A"],
    ["Preparing or fixing input layers", "Chapter 3"],
    ["Looking up what a specific control does", "Chapter 4"],
    ["Getting a route onto a GPS or phone", "Chapter 6"],
    ["Automating this for many fields", "Chapter 7"],
    ["Taking over maintenance of the plugin", "Chapter 8, Part B"],
  ];
  kids.push(makeTable(guideRows));
  kids.push(new Paragraph({ spacing: { after: 200 }, children: [new TextRun("")] }));

  [
    "**A note on terminology.** The plugin is called *Plover*, but the folder it installs into is called `tsp_route_generator`. That is deliberate: QGIS identifies plugins by folder name, so renaming it would break existing installations.",
    "**Screenshots.** The dialog screenshots in this guide were captured from the plugin itself at version " + VERSION + ". Your QGIS theme may render the controls in different colours, but the labels and layout will match.",
  ].forEach((t) => kids.push(body(t)));

  return kids;
}

// ----------------------------------------------------------------------- main

function main() {
  const children = titlePage();

  ORDER.forEach((key, idx) => {
    const file = path.join(CHAPTERS, `${key}.md`);
    if (!fs.existsSync(file)) { console.warn(`  ! missing chapter: ${key}`); return; }
    const md = fs.readFileSync(file, "utf8");
    const chapterNum = key === "appendix" ? "A" : String(idx + 1);
    const state = { fig: 0 };
    const parsed = parseMarkdown(md, chapterNum, state);
    children.push(...parsed);
    console.log(`  + ${key.padEnd(11)} ${parsed.length} blocks, ${state.fig} figures`);
  });

  const doc = new Document({
    creator: "Plover",
    title: "Plover User Guide",
    description: `Plover ${VERSION} - complete user guide`,
    numbering: {
      config: [
        {
          reference: "bul",
          levels: [{
            level: 0, format: LevelFormat.BULLET, text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 420, hanging: 220 } } },
          }],
        },
        {
          reference: "num",
          levels: [{
            level: 0, format: LevelFormat.DECIMAL, text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 260 } } },
          }],
        },
      ],
    },
    styles: {
      default: {
        document: { run: { font: "Calibri", size: 21, color: INK } },
      },
    },
    sections: [{
      properties: {
        titlePage: true,
        page: {
          size: { width: 12240, height: 15840 },     // US Letter
          margin: { top: 1180, right: 1440, bottom: 1180, left: 1440 },
        },
      },
      headers: {
        first: new Header({ children: [new Paragraph({ children: [new TextRun("")] })] }),
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            spacing: { after: 60 },
            border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } },
            children: [new TextRun({
              text: `Plover User Guide  ·  v${VERSION}`, size: 16, color: MUTED,
            })],
          })],
        }),
      },
      footers: {
        first: new Footer({ children: [new Paragraph({ children: [new TextRun("")] })] }),
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({
              children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES],
              size: 16, color: MUTED,
            })],
          })],
        }),
      },
      children,
    }],
  });

  const out = path.join(REPO, "docs", "Plover-User-Guide.docx");
  return Packer.toBuffer(doc).then((buf) => {
    fs.writeFileSync(out, buf);
    console.log(`\nWrote ${path.relative(REPO, out)} (${(buf.length / 1024).toFixed(0)} KB)`);
  });
}

main().catch((e) => { console.error(e); process.exit(1); });

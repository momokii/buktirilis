import { Link } from "react-router-dom";
import { TableWrap } from "../ui";
import { guideFigureUrls } from "../content/guide/content";
import { FIGURE_META } from "../content/guide/figureMeta";
import { parseInline, type GuideBlock } from "../content/guide/parse";

function Inline({ text }: { text: string }) {
  return (
    <>
      {parseInline(text).map((token, index) => {
        if (token.kind === "strong") return <strong key={index}>{token.text}</strong>;
        if (token.kind === "code") {
          return (
            <code className="mono" key={index}>
              {token.text}
            </code>
          );
        }
        if (token.kind === "link") {
          if (token.href.startsWith("/")) {
            return (
              <Link key={index} to={token.href}>
                {token.text}
              </Link>
            );
          }
          if (token.href.startsWith("#")) {
            return (
              <a key={index} href={token.href}>
                {token.text}
              </a>
            );
          }
          if (token.href.startsWith("https://")) {
            return (
              <a key={index} href={token.href} rel="noopener noreferrer">
                {token.text}
              </a>
            );
          }
          return <span key={index}>{token.text}</span>;
        }
        return <span key={index}>{token.text}</span>;
      })}
    </>
  );
}

export function GuideBlocks({ blocks }: { blocks: GuideBlock[] }) {
  const firstFigure = blocks.findIndex((block) => block.kind === "figure");
  return (
    <>
      {blocks.map((block, index) => {
        if (block.kind === "figure") {
          const { url, url2x } = guideFigureUrls(block.src);
          const meta = FIGURE_META[block.src];
          return (
            <figure className="guide-figure" key={index}>
              <img
                src={url}
                srcSet={url2x ? `${url} 1x, ${url2x} 2x` : undefined}
                width={meta?.width}
                height={meta?.height}
                alt={block.alt}
                loading={index === firstFigure ? "eager" : "lazy"}
                decoding="async"
              />
              <figcaption>
                <strong>Figure {block.number}.</strong> <Inline text={block.caption} />
              </figcaption>
            </figure>
          );
        }
        if (block.kind === "heading") {
          const Heading = `h${block.level}` as "h1" | "h2" | "h3";
          return (
            <Heading className="guide-heading" id={block.id} key={index} tabIndex={-1}>
              <Inline text={block.text} />
            </Heading>
          );
        }
        if (block.kind === "paragraph") {
          return (
            <p key={index}>
              <Inline text={block.text} />
            </p>
          );
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <Inline text={item} />
                </li>
              ))}
            </List>
          );
        }
        if (block.kind === "code") {
          return (
            <pre
              className="code guide-code"
              key={index}
              tabIndex={0}
              role="region"
              aria-label={block.language ? `${block.language} code example` : "Code example"}
            >
              <code>{block.text}</code>
            </pre>
          );
        }
        if (block.kind === "table") {
          const label = block.caption ?? "Guide table";
          return (
            <TableWrap key={index} label={label}>
              <table>
                {block.caption ? <caption>{block.caption}</caption> : null}
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th key={headerIndex} scope="col">
                        <Inline text={header} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>
                          <Inline text={cell} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          );
        }
        return (
          <div className={`notice notice-${block.tone}`} key={index} role="note">
            <div>
              <strong>{block.title}</strong>
              <p>
                <Inline text={block.text} />
              </p>
            </div>
          </div>
        );
      })}
    </>
  );
}

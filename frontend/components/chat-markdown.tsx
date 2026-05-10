"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight, vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import { useTheme } from "next-themes";

const markdownComponents: Components = {
  code(props) {
    const { className, children } = props;
    const match = /language-(\w+)/.exec(className ?? "");
    const content = String(children).replace(/\n$/, "");

    if (match) {
      return <CodeBlock language={match[1]}>{content}</CodeBlock>;
    }

    return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.92em]">{children}</code>;
  },
};

function CodeBlock({ language, children }: { language: string; children: string }) {
  const { resolvedTheme } = useTheme();

  return (
    <SyntaxHighlighter
      language={language}
      style={resolvedTheme === "dark" ? vscDarkPlus : oneLight}
      customStyle={{
        borderRadius: "1rem",
        margin: 0,
        padding: "1rem",
        fontSize: "0.875rem",
      }}
    >
      {children}
    </SyntaxHighlighter>
  );
}

export function ChatMarkdown({ content }: { content: string }) {
  return (
    <div className="markdown-body text-sm leading-7 text-foreground/92">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

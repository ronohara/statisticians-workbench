"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

const components = {
    a: ({ node, ...props }: any) => (
        <a {...props} className="text-primary underline" target="_blank" rel="noreferrer" />
    ),
    p: ({ node, ...props }: any) => <p className="my-1" {...props} />,
    ul: ({ node, ...props }: any) => <ul className="list-disc ps-5 my-1" {...props} />,
    ol: ({ node, ...props }: any) => <ol className="list-decimal ps-5 my-1" {...props} />,
    code: ({ node, ...props }: any) => (
        <code className="bg-muted rounded px-1 py-0.5 text-xs" {...props} />
    ),
    table: ({ node, ...props }: any) => (
        <div className="overflow-x-auto my-2">
            <table className="border-collapse w-full text-xs" {...props} />
        </div>
    ),
    th: ({ node, ...props }: any) => (
        <th className="border border-border px-2 py-1 text-left font-medium bg-muted" {...props} />
    ),
    td: ({ node, ...props }: any) => (
        <td className="border border-border px-2 py-1" {...props} />
    ),
};

export default function MarkdownContent({ children }: { children: string }) {
    return (
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>
            {children}
        </ReactMarkdown>
    );
}

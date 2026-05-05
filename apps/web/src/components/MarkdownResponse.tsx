import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";

type MarkdownResponseProps = {
  content: string;
};

export default function MarkdownResponse({ content }: MarkdownResponseProps) {
  return (
    <div className="markdown-response">
      <ReactMarkdown
        remarkPlugins={[remarkBreaks]}
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Test component to verify ReactMarkdown is working
 * 
 * Usage: Import and add to your app temporarily to test
 */
export const MarkdownTest: React.FC = () => {
  const testMarkdown = `## Test Header

**Bold text** and *italic text*

- List item 1
- List item 2

| Column 1 | Column 2 |
|----------|----------|
| Cell 1   | Cell 2   |

\`inline code\`

\`\`\`
code block
\`\`\`
`;

  return (
    <div className="p-4 border-2 border-red-500">
      <h1 className="text-2xl font-bold mb-4">Markdown Test</h1>
      
      <div className="mb-4">
        <h2 className="font-bold">Raw Content:</h2>
        <pre className="bg-gray-100 p-2 text-xs">{testMarkdown}</pre>
      </div>
      
      <div className="mb-4">
        <h2 className="font-bold">Rendered with ReactMarkdown:</h2>
        <div className="prose prose-sm max-w-full dark:prose-invert border-2 border-blue-500 p-2">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {testMarkdown}
          </ReactMarkdown>
        </div>
      </div>
      
      <div>
        <h2 className="font-bold">Expected:</h2>
        <ul className="list-disc ml-4">
          <li>Header should be large and bold</li>
          <li>Bold and italic should be styled</li>
          <li>List should have bullets</li>
          <li>Table should be formatted</li>
          <li>Code should be highlighted</li>
        </ul>
      </div>
    </div>
  );
};

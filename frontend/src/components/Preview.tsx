export default function Preview({ html }: { html: string | null }) {
  return (
    <div className="preview">
      {html ? (
        <iframe
          className="preview__frame"
          srcDoc={html}
          sandbox="allow-scripts allow-forms allow-popups"
          title="Live preview"
        />
      ) : (
        <div className="preview__placeholder">Your site will appear here</div>
      )}
    </div>
  )
}

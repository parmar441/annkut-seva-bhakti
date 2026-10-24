import { Component, type ErrorInfo, type ReactNode } from 'react';

/** Last line of defence: a rendering bug shows a recovery screen instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unexpected UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="auth" role="alert">
        <div className="brand">
          <h1>Something went wrong</h1>
          <p>Your seva time is safe on the server. Reload the page to continue.</p>
        </div>
        <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 32 }} onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    );
  }
}

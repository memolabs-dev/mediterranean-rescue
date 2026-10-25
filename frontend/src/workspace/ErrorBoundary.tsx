import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: (error: Error, info: ErrorInfo) => ReactNode;
}

interface State {
  error: Error | null;
  info: ErrorInfo | null;
}

/**
 * Catches render errors in children and displays them instead of a blank page.
 * Without this, a crash in any child of WorkspaceShell unmounts the entire shell.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, info: null };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ info: errorInfo });
  }

  render() {
    const error = this.state.error;
    if (error) {
      const fallback = this.props.fallback;
      if (fallback) return fallback(error, this.state.info!);
      return (
        <div style={{ padding: 16, color: "#b00" }}>
          <h2>Render error</h2>
          <pre>{error.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

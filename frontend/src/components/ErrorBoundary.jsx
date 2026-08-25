import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // A real deployment would send this to a logging service. For a
    // student project, console logging is sufficient — the point of
    // the boundary is preventing a full white-screen crash, not
    // building production-grade observability.
    console.error("EquityEngine rendering error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4 text-center">
          <div>
            <h1 className="text-xl font-display font-semibold">Something went wrong.</h1>
            <p className="text-slate mt-2 text-sm max-w-sm">
              This page ran into an error. Try reloading — if it keeps happening, it's worth
              reporting.
            </p>
            <button onClick={() => window.location.reload()} className="btn-primary mt-4">
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

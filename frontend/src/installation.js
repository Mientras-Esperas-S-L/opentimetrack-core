// The name people see in this installation: OpenTimeTrack, unless it sets its own
// when the web is built (VITE_INSTALLATION_NAME, or the server's INSTALLATION_NAME;
// see vite.config.js). A company that runs the Core as a part of its own product
// shows that product's name. A proper name, so it is never translated.
export const INSTALLATION_NAME = (import.meta.env.VITE_INSTALLATION_NAME || '').trim() || 'OpenTimeTrack'

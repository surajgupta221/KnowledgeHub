import { useState, useEffect } from 'react';
import './Login.css';

export default function Login({ onLoginSuccess }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load user from sessionStorage on mount
    const storedUser = sessionStorage.getItem('current_user');
    if (storedUser) {
      setCurrentUser(storedUser);
      onLoginSuccess(storedUser);
    }
    setLoading(false);
  }, [onLoginSuccess]);

  const handleLogin = (userId) => {
    sessionStorage.setItem('current_user', userId);
    setCurrentUser(userId);
    onLoginSuccess(userId);
  };

  if (loading) {
    return null;
  }

  if (currentUser) {
    return (
      <div className="login-bar">
        <span className="user-info">👤 Logged in as: <strong>{currentUser}</strong></span>
        <button
          className="btn-logout"
          onClick={() => {
            sessionStorage.removeItem('current_user');
            setCurrentUser(null);
          }}
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>KnowledgeHub</h2>
        <p>Policy document assistant with streaming QA</p>

        <div className="login-buttons">
          <button
            className="btn-login btn-user-a"
            onClick={() => handleLogin('user_a')}
          >
            Login as User A
          </button>
          <button
            className="btn-login btn-user-b"
            onClick={() => handleLogin('user_b')}
          >
            Login as User B
          </button>
        </div>

        <p className="login-note">
          👉 <strong>Demo Instructions:</strong> Log in as User A, upload a document,<br/>
          then logout and log in as User B to verify access control.
        </p>
      </div>
    </div>
  );
}

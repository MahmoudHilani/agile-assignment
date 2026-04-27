'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        setError('Invalid credentials');
        return;
      }
      const data = await res.json();
      localStorage.setItem('admin_token', data.access_token);
      router.push('/');
    } catch {
      setError('Could not connect to server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#f8fafc',
      fontFamily: 'system-ui, sans-serif',
    }}>
      <form
        onSubmit={handleSubmit}
        style={{
          width: '320px',
          padding: '32px',
          borderRadius: '18px',
          backgroundColor: '#ffffff',
          boxShadow: '0 18px 40px rgba(15, 23, 42, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <h1 style={{ margin: 0, fontSize: '1.25rem', color: '#0f172a', textAlign: 'center' }}>
          Admin Login
        </h1>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '0.875rem', color: '#475569' }}>Username</label>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            style={{
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1.5px solid #e2e8f0',
              fontSize: '0.95rem',
              outline: 'none',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '0.875rem', color: '#475569' }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1.5px solid #e2e8f0',
              fontSize: '0.95rem',
              outline: 'none',
            }}
          />
        </div>

        {error && (
          <p style={{ margin: 0, color: '#ef4444', fontSize: '0.875rem', textAlign: 'center' }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '11px',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: loading ? '#94a3b8' : '#6366f1',
            color: '#ffffff',
            fontSize: '0.95rem',
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}

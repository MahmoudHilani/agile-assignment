import React from 'react';

const VoiceWave = ({ isListening }: { isListening: boolean }) => {
  
  const bars = [1, 2, 3, 4, 5];

  if (!isListening) return null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      height: '20px',
      padding: '0 10px'
    }}>
      {bars.map((bar) => (
        <div
          key={bar}
          className="voice-bar"
          style={{
            width: '3px',
            backgroundColor: '#4f46e5',
            borderRadius: '2px',
          }}
        />
      ))}
      <style jsx>{`
        .voice-bar {
          animation: wave 1s ease-in-out infinite;
        }
        .voice-bar:nth-child(1) { animation-delay: 0.1s; height: 10px; }
        .voice-bar:nth-child(2) { animation-delay: 0.3s; height: 18px; }
        .voice-bar:nth-child(3) { animation-delay: 0.2s; height: 14px; }
        .voice-bar:nth-child(4) { animation-delay: 0.4s; height: 20px; }
        .voice-bar:nth-child(5) { animation-delay: 0.1s; height: 12px; }

        @keyframes wave {
          0%, 100% { transform: scaleY(0.5); }
          50% { transform: scaleY(1.5); }
        }
      `}</style>
    </div>
  );
};

export default VoiceWave;
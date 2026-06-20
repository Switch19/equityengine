import { useState, useEffect, useRef } from 'react'
import api from '../services/api'

export default function ChatBox({ jobId, senderId, receiverId, receiverName }) {
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  const fetchMessages = async () => {
    try {
      const res = await api.get(`/messages/${jobId}/${senderId}/${receiverId}`)
      setMessages(res.data.messages)
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    fetchMessages()
    const interval = setInterval(fetchMessages, 5000)
    return () => clearInterval(interval)
  }, [jobId, senderId, receiverId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!newMessage.trim()) return
    setLoading(true)
    try {
      await api.post('/messages/send', {
        sender_id: senderId,
        receiver_id: receiverId,
        job_id: jobId,
        content: newMessage.trim()
      })
      setNewMessage('')
      fetchMessages()
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="border border-gray-200 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="bg-blue-600 px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-blue-400 flex items-center justify-center text-white text-sm font-bold">
          {receiverName?.charAt(0) || '?'}
        </div>
        <div>
          <p className="text-white font-medium text-sm">{receiverName}</p>
          <p className="text-blue-200 text-xs">Interview conversation</p>
        </div>
      </div>

      {/* Messages */}
      <div className="h-64 overflow-y-auto p-4 bg-gray-50 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm mt-8">
            No messages yet. Start the conversation!
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.sender_id === senderId ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-xs px-4 py-2 rounded-2xl text-sm ${
              msg.sender_id === senderId
                ? 'bg-blue-600 text-white rounded-br-none'
                : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
            }`}>
              <p>{msg.content}</p>
              <p className={`text-xs mt-1 ${msg.sender_id === senderId ? 'text-blue-200' : 'text-gray-400'}`}>
                {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 bg-white border-t border-gray-200 flex gap-2">
        <input
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type a message..."
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleSend}
          disabled={!newMessage.trim() || loading}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm transition disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
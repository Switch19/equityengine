import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import ChatBox from '../components/ChatBox'
import api from '../services/api'

export default function Messages() {
  const [conversations, setConversations] = useState([])
  const [selected, setSelected] = useState(null)
  const userId = parseInt(localStorage.getItem('user_id') || '1')
  const role = localStorage.getItem('role')

  useEffect(() => {
    api.get(`/messages/inbox/${userId}`)
      .then(res => setConversations(res.data.conversations))
      .catch(err => console.error(err))
  }, [userId])

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">Messages 💬</h2>
        <p className="text-gray-500 mb-8">Your interview conversations.</p>

        {conversations.length === 0 && (
          <div className="bg-white rounded-2xl p-8 text-center border border-gray-100">
            <p className="text-gray-400">No conversations yet.</p>
            <p className="text-sm text-gray-400 mt-1">
              {role === 'recruiter'
                ? 'Request an interview to start a conversation with a candidate.'
                : 'When a recruiter requests an interview, your conversation will appear here.'}
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Conversation List */}
          {conversations.length > 0 && (
            <div className="md:col-span-1 space-y-2">
              {conversations.map((conv, i) => (
                <div
                  key={i}
                  onClick={() => setSelected(conv)}
                  className={`bg-white rounded-xl border p-4 cursor-pointer transition ${
                    selected?.other_user_id === conv.other_user_id
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-100 hover:border-blue-200'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-sm">
                      {conv.other_user_name?.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-800 text-sm truncate">{conv.other_user_name}</p>
                      <p className="text-xs text-gray-400 truncate">{conv.last_message}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Chat Window */}
          {selected && (
            <div className="md:col-span-2">
              <ChatBox
                jobId={selected.job_id}
                senderId={userId}
                receiverId={selected.other_user_id}
                receiverName={selected.other_user_name}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
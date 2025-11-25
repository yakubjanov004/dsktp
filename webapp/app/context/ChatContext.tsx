"use client"

import { createContext, useContext, useState, useEffect, ReactNode, useRef, useCallback } from "react"
import {
  getChats,
  getChat,
  getChatMessages,
  createChat,
  sendMessage as apiSendMessage,
  closeChat as apiCloseChat,
  ChatWebSocket,
  StatsWebSocket,
  StaffChatWebSocket,
  type Chat,
  type Message,
  type ClientInfo,
  getClientInfo,
  getAvailableClients,
  getOperators,
  markInactiveChats,
  getInbox,
  getActiveChats,
  getMyChats,
  getActiveChatStats,
  type ActiveChatStats,
  getStaffChats,
  createStaffChat,
  getStaffChat,
  getStaffChatMessages,
  sendStaffMessage as apiSendStaffMessage,
  getAvailableStaff,
  type StaffChat,
} from "../lib/api"

// Convert database Chat to ChatSession format
interface ChatSession {
  id: string
  clientId: string
  operatorId: string | null
  status: "active" | "inactive"
  createdAt: Date
  lastActivity: Date
  lastClientActivityAt?: string | null
  messages: Message[]
  lastMessage: Message | null
  clientName?: string
  operatorName?: string | null
}

interface ChatContextType {
  chatSessions: ChatSession[]
  staffChats: ChatSession[]
  users: ClientInfo[]
  activeChats: string[]
  typingUsers: Record<string, boolean>
  unreadCounts: Record<string, number>
  isLoading: boolean
  activeChatStats: ActiveChatStats | null
  onlineUsers: Set<number>
  sendMessage: (chatId: string, message: string, senderId: number) => Promise<void>
  closeChat: (chatId: string) => Promise<void>
  startNewChat: (clientId: number) => Promise<string | null>
  markAsRead: (chatId: string, userId: number) => void
  addToActiveChats: (chatId: string) => void
  removeFromActiveChats: (chatId: string) => void
  refreshChats: () => Promise<void>
  loadChats: () => Promise<void>
  loadChatMessages: (chatId: string, force?: boolean) => Promise<void>
  loadInbox: (limit?: number, cursorTs?: string, cursorId?: number) => Promise<void>
  loadActiveChats: (limit?: number, cursorTs?: string, cursorId?: number) => Promise<void>
  loadMyChats: (limit?: number, cursorTs?: string, cursorId?: number) => Promise<void>
  loadActiveChatStats: () => Promise<void>
  // Staff chat functions
  loadStaffChats: () => Promise<void>
  startStaffChat: (receiverId: number) => Promise<string | null>
  sendStaffMessage: (chatId: string, message: string, senderId: number) => Promise<void>
  loadStaffChatMessages: (chatId: string, force?: boolean) => Promise<void>
  // Auto-open chat callback
  onNewMessage?: (chatId: string) => void
  setOnNewMessage?: (callback: ((chatId: string) => void) | null) => void
}

const sortChatsByLastActivity = (sessions: ChatSession[]) =>
  [...sessions].sort((a, b) => b.lastActivity.getTime() - a.lastActivity.getTime())

const ChatContext = createContext<ChatContextType | undefined>(undefined)

interface ChatProviderProps {
  children: ReactNode
  telegramId?: number
  userId?: number
  userRole?: string
}

export function ChatProvider({ children, telegramId, userId, userRole }: ChatProviderProps) {
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [staffChats, setStaffChats] = useState<ChatSession[]>([])
  const [users, setUsers] = useState<ClientInfo[]>([])
  const [activeChats, setActiveChats] = useState<string[]>([])
  const [typingUsers, setTypingUsers] = useState<Record<string, boolean>>({})
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [activeChatStats, setActiveChatStats] = useState<ActiveChatStats | null>(null)
  const [onlineUsers, setOnlineUsers] = useState<Set<number>>(new Set())
  
  // Store userId and userRole in refs for use in callbacks
  const userIdRef = useRef<number | undefined>(userId)
  const userRoleRef = useRef<string | undefined>(userRole)
  const telegramIdRef = useRef<number | undefined>(telegramId)
  
  // Update refs when props change
  useEffect(() => {
    userIdRef.current = userId
    userRoleRef.current = userRole
    telegramIdRef.current = telegramId
  }, [userId, userRole, telegramId])
  
  // Store WebSocket connections - single connection per chat
  const wsConnections = useRef<Map<string, ChatWebSocket>>(new Map())
  // Store staff chat WebSocket connections
  const staffWsConnections = useRef<Map<string, StaffChatWebSocket>>(new Map())
  // Store stats WebSocket connection
  const statsWsRef = useRef<StatsWebSocket | null>(null)
  // Track which chats have messages loaded (prevent duplicate calls)
  const loadedMessagesRef = useRef<Set<string>>(new Set())
  // Callback for auto-opening chat when new message arrives
  const onNewMessageRef = useRef<((chatId: string) => void) | null>(null)
  // Track loading state for each chat
  const loadingMessagesRef = useRef<Set<string>>(new Set())
  // Track last message ID and timestamp for sync after reconnect
  const lastMessageDataRef = useRef<Record<string, { id: number; ts: string }>>({})
  // Track currently subscribed chat IDs to prevent duplicate subscriptions (Set for multiple chats)
  const subscribedChatIdsRef = useRef<Set<string>>(new Set())
  
  // Debouncing and caching
  const lastFetchTime = useRef<Record<string, number>>({})
  const cacheTimeout = 2000 // 2 seconds
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  
  // Store load functions in refs for use in event handlers
  const loadInboxRef = useRef<((limit?: number, cursorTs?: string, cursorId?: number) => Promise<void>) | null>(null)
  const loadActiveChatsRef = useRef<((limit?: number, cursorTs?: string, cursorId?: number) => Promise<void>) | null>(null)
  const loadMyChatsRef = useRef<((limit?: number, cursorTs?: string, cursorId?: number) => Promise<void>) | null>(null)
  
  // Convert Chat to ChatSession
  const convertChatToSession = useCallback((chat: Chat): ChatSession => {
    return {
      id: chat.id.toString(),
      clientId: chat.client_id.toString(),
      operatorId: chat.operator_id?.toString() || null,
      status: chat.status,
      createdAt: new Date(chat.created_at),
      lastActivity: new Date(chat.last_activity_at || chat.updated_at || Date.now()),
      lastClientActivityAt: chat.last_client_activity_at || null,
      messages: [],
      lastMessage: null,
      clientName: chat.client_name,
      operatorName: chat.operator_name,
    }
  }, [])
  
  const upsertChatSession = useCallback((chatData: Chat) => {
    if (!chatData || !chatData.id) return
    const session = convertChatToSession(chatData)
    setChatSessions((prev) => {
      const index = prev.findIndex((chat) => chat.id === session.id)
      if (index >= 0) {
        const existing = prev[index]
        const updated = {
          ...existing,
          ...session,
          messages: existing.messages,
          lastMessage: existing.lastMessage,
        }
        const next = [...prev]
        next[index] = updated
        return sortChatsByLastActivity(next)
      }
      return sortChatsByLastActivity([session, ...prev])
    })
  }, [convertChatToSession])

  const fetchChatAndUpsert = useCallback(async (chatId: number) => {
    try {
      const chat = await getChat(chatId)
      if (chat) {
        upsertChatSession(chat)
        return chat
      }
    } catch (error) {
      console.error(`Error fetching chat ${chatId}:`, error)
    }
    return null
  }, [upsertChatSession])

  // Store initializeWebSocket function in ref for use in loadChatMessages
  const initializeWebSocketRef = useRef<((chatId: string, userId: number) => void) | null>(null)
  
  // Initialize WebSocket connection for a chat - single connection per chat
  const initializeWebSocket = useCallback((chatId: string, userId: number) => {
    console.log(`🔗 [WS] Attempting to connect: chat=${chatId}, user=${userId}, role=${userRoleRef.current}`);
    console.log(`⚡ [WS-INIT] Called with chatId: ${chatId}, userId: ${userId}, userRole: ${userRoleRef.current}`)
    
    // Skip WebSocket in development if not available
    if (typeof window === 'undefined' || !window.WebSocket) {
      console.warn('[ChatContext] WebSocket not available - window:', typeof window, 'WebSocket:', typeof window?.WebSocket)
      return
    }
    
    // Validate userId
    if (!userId || userId <= 0) {
      console.error('[ChatContext] initializeWebSocket: Invalid userId:', userId, 'chatId:', chatId)
      return
    }
    
    const currentTelegramId = telegramIdRef.current
    if (!currentTelegramId || currentTelegramId <= 0) {
      console.warn('[ChatContext] initializeWebSocket: Missing telegramId, delaying WS connection', { chatId, userId })
      return
    }
    
    // Prevent duplicate subscription - if already subscribed to this chat, skip
    if (subscribedChatIdsRef.current.has(chatId)) {
      const existing = wsConnections.current.get(chatId)
      if (existing && existing.isConnected()) {
        // Already connected to this chat and connection is open
        console.log('[ChatContext] initializeWebSocket: Already connected to chat:', chatId, 'userId:', userId, 'readyState:', existing.getReadyState())
        return
      } else if (existing) {
        // Connection exists but is not open - clean it up
        console.log('[ChatContext] initializeWebSocket: Existing connection is not open, cleaning up. chat:', chatId, 'readyState:', existing.getReadyState())
        try {
          existing.disconnect()
        } catch (e) {
          console.warn('[ChatContext] initializeWebSocket: Error disconnecting existing:', e)
        }
        wsConnections.current.delete(chatId)
        subscribedChatIdsRef.current.delete(chatId)
      } else {
        // Connection was lost but still in set - remove it
        console.log('[ChatContext] initializeWebSocket: Removing stale subscription for chat:', chatId)
        subscribedChatIdsRef.current.delete(chatId)
      }
    }
    
    // Close any existing connection for this chat (reconnect scenario)
    const existing = wsConnections.current.get(chatId)
    if (existing) {
      console.log('[ChatContext] initializeWebSocket: Closing existing connection for chat:', chatId)
      try {
        existing.disconnect()
      } catch (e) {
        console.warn('[ChatContext] initializeWebSocket: Error disconnecting existing:', e)
      }
      wsConnections.current.delete(chatId)
    }

    try {
      console.log(`✅ [WS-CREATE] Creating WebSocket: chat=${chatId}, user=${userId}, role=${userRoleRef.current}`)
      const ws = new ChatWebSocket(
        parseInt(chatId),
        currentTelegramId,
        userId,
        (message: Message) => {
          // Handle chat.message event from WebSocket - real-time update
          // This works for both client and operator - message is broadcast to all chat participants
          const messageChatId = message.chat_id.toString()
          
          console.log('[ChatContext] WebSocket message received:', { 
            chatId: messageChatId, 
            messageId: message.id, 
            senderType: message.sender_type, 
            senderId: message.sender_id,
            messageText: message.message_text?.substring(0, 50),
            currentUserId: userIdRef.current,
            currentUserRole: userRoleRef.current
          })
          
          setChatSessions((prev) => {
            console.log('[ChatContext] setChatSessions: Current chats:', prev.map(c => ({ id: c.id, messageCount: c.messages.length })))
            // Find chat by ID (can be different from subscribed chatId if multiple chats)
            const chatIndex = prev.findIndex((chat) => chat.id === messageChatId)
            console.log('[ChatContext] setChatSessions: Chat index found:', chatIndex, 'for chatId:', messageChatId)
            
            if (chatIndex >= 0) {
              // Chat exists - update it
              const chat = prev[chatIndex]
              
              // Update last message tracking
              lastMessageDataRef.current[messageChatId] = {
                id: message.id,
                ts: message.created_at
              }
              
              // Check if message already exists (by ID) - prevent duplicates
              const existingIndex = chat.messages.findIndex((m) => m.id === message.id)
              
              if (existingIndex >= 0) {
                // Message already exists - update it with latest data (e.g., sender_name, read_at)
                const updatedMessages = [...chat.messages]
                updatedMessages[existingIndex] = message
                
                const updated = [...prev]
                updated[chatIndex] = {
                  ...chat,
                  messages: updatedMessages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
                  lastMessage: message,
                  lastActivity: new Date(message.created_at),
                }
                return updated
              } else {
                // New message - check if it's a replacement for temporary message
                // Look for temp message with negative ID and matching text/timestamp
                const tempIndex = chat.messages.findIndex((m) => 
                  m.id < 0 && // Temporary message has negative ID
                  m.message_text === message.message_text && 
                  Math.abs(new Date(m.created_at).getTime() - new Date(message.created_at).getTime()) < 10000) // Within 10 seconds
                
                if (tempIndex >= 0) {
                  // Replace temporary message with real one - this prevents duplicates
                  const updatedMessages = [...chat.messages]
                  updatedMessages[tempIndex] = message
                  
                  const updated = [...prev]
                  updated[chatIndex] = {
                    ...chat,
                    messages: updatedMessages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
                    lastMessage: message,
                    lastActivity: new Date(message.created_at),
                  }
                  return updated
                } else {
                  // Completely new message - add it (from other participant)
                  console.log('[ChatContext] Adding new message to chat:', messageChatId, 'messageId:', message.id, 'current messages count:', chat.messages.length)
                  const updated = [...prev]
                  const newMessages = [...chat.messages, message].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
                  updated[chatIndex] = {
                    ...chat,
                    messages: newMessages,
                    lastMessage: message,
                    lastActivity: new Date(message.created_at),
                  }
                  console.log('[ChatContext] Updated chat:', messageChatId, 'new messages count:', newMessages.length, 'lastMessage:', message.id)
                  
                  // Auto-open chat window if callback is set (for operators/supervisors)
                  // Only if chat window is not already open
                  if (onNewMessageRef.current) {
                    console.log('[ChatContext] Calling onNewMessage callback for chat:', messageChatId)
                    onNewMessageRef.current(messageChatId)
                  }
                  
                  return updated
                }
              }
            } else {
              // Chat doesn't exist in sessions - create minimal chat with this message
              // This can happen if operator opens a chat that wasn't loaded yet
              console.log(`[ChatContext] WebSocket message for chat ${messageChatId} not in sessions, creating minimal chat`)
              const minimalChat: ChatSession = {
                id: messageChatId,
                clientId: message.sender_type === 'client' ? (message.sender_id?.toString() || '') : '',
                operatorId: message.sender_type === 'operator' ? (message.sender_id?.toString() || null) : null,
                status: 'active',
                createdAt: new Date(message.created_at),
                lastActivity: new Date(message.created_at),
                messages: [message],
                lastMessage: message,
              }
              
              // Update last message tracking
              lastMessageDataRef.current[messageChatId] = {
                id: message.id,
                ts: message.created_at
              }
              
              return [...prev, minimalChat]
            }
          })
        },
        (userId: number, isTyping: boolean) => {
          setTypingUsers((prev) => ({
            ...prev,
            [`${chatId}-${userId}`]: isTyping,
          }))
        },
        (error: Error) => {
          console.error(`WebSocket error for chat ${chatId}:`, error)
          // Fallback to polling - don't show error
        },
        (chatId: number, operatorId: number) => {
          // Handle chat.assigned event - update chat state
          setChatSessions((prev) =>
            prev.map((chat) => {
              if (chat.id === chatId.toString()) {
                return {
                  ...chat,
                  operatorId: operatorId.toString(),
                  status: "active" as const,
                }
              }
              return chat
            })
          )
          // Update stats if needed (event-driven)
          loadActiveChatStats()
        },
        (inactiveChatId: number) => {
          // Handle chat.inactive event - update chat state
          setChatSessions((prev) =>
            prev.map((chat) => {
              if (chat.id === inactiveChatId.toString()) {
                return {
                  ...chat,
                  status: "inactive" as const,
                }
              }
              return chat
            })
          )
          // Update stats if needed (event-driven)
          loadActiveChatStats()
        },
        () => {
          // Handle reconnect - sync messages with since_ts/since_id
          const lastData = lastMessageDataRef.current[chatId]
          if (lastData) {
            console.log(`Syncing messages after reconnect for chat ${chatId}`)
            loadChatMessages(chatId, false, lastData.ts, lastData.id).catch(err => {
              console.error(`Error syncing messages after reconnect:`, err)
            })
          }
        }
      )

      // Connect WebSocket - reconnect logic is handled by ChatWebSocket class with exponential backoff
      console.log(`🔌 [WS-CONNECT] Connecting to WebSocket endpoint: chat=${chatId}, user=${userId}`)
      ws.connect()
      wsConnections.current.set(chatId, ws)
      subscribedChatIdsRef.current.add(chatId)
      console.log(`✨ [WS-ONLINE] WebSocket connected and ready: chat=${chatId}, user=${userId}`)
    } catch (error) {
      console.warn(`Failed to initialize WebSocket for chat ${chatId}:`, error)
      // Fallback to polling - don't show error
    }
  }, [])
  
  // Store initializeWebSocket in ref for use in loadChatMessages
  useEffect(() => {
    initializeWebSocketRef.current = initializeWebSocket
  }, [initializeWebSocket])

  // Load messages for a specific chat (with sync support via since_ts/since_id)
  // Defined before loadChats so it can be used in loadChats
  const loadChatMessages = useCallback(async (chatId: string, force: boolean = false, sinceTs?: string, sinceId?: number) => {
    // If forced, reset loaded state to ensure fresh reload
    if (force) {
      loadedMessagesRef.current.delete(chatId)
    }
    
    // Prevent duplicate simultaneous calls (unless forced)
    if (!force && loadingMessagesRef.current.has(chatId)) {
      return
    }
    
    // If forced, always reload (for persistence - get latest messages from database)
    // Otherwise check if messages are already loaded
    if (!force && loadedMessagesRef.current.has(chatId)) {
      return
    }
    
    loadingMessagesRef.current.add(chatId)
    
    try {
      // First, ensure chat exists in sessions
      setChatSessions((prev) => {
        const chatExists = prev.some((chat) => chat.id === chatId)
        if (!chatExists) {
          // Try to load chat by ID (for supervisors viewing any chat)
          // This will be handled asynchronously, so we'll load messages anyway
          console.warn(`Chat ${chatId} not found in sessions. Will try to load chat first.`)
        }
        return prev
      })
      
      // Check if chat exists in sessions
      // For clients, chat should already be loaded via loadChats, but we'll proceed anyway
      // For supervisors/operators, try to load chat if it doesn't exist
      let chatExists = false
      setChatSessions((prev) => {
        chatExists = prev.some((chat) => chat.id === chatId)
        return prev
      })
      
      // Only try to load chat if it doesn't exist AND user is not a client
      // For clients, even if chat doesn't exist in sessions yet (async state update),
      // we'll still load messages - they will be attached when chat is added
      if (!chatExists && userRoleRef.current !== 'client') {
        try {
          const chat = await getChat(parseInt(chatId))
          if (chat) {
            const session = convertChatToSession(chat)
            setChatSessions((prev) => {
              // Check again to avoid duplicates
              if (prev.some((c) => c.id === chatId)) {
                return prev
              }
              return [...prev, session]
            })
            chatExists = true
          }
        } catch (error) {
          console.error(`Error loading chat ${chatId}:`, error)
        }
      }
      
      // For clients: if chat doesn't exist yet, log warning but continue loading messages
      // The chat will be added to sessions soon (from loadChats), and messages will be attached
      if (!chatExists && userRoleRef.current === 'client') {
        console.log(`[ChatContext] loadChatMessages: Chat ${chatId} not in sessions yet for client, but proceeding to load messages anyway`)
      }
      
      // Load messages - use since_ts/since_id for sync, otherwise load initial batch
      // For force=true (when entering chat), load ALL messages to show full chat history
      console.log('[ChatContext] loadChatMessages: Loading messages for chatId:', chatId, 'force:', force, 'sinceTs:', sinceTs, 'sinceId:', sinceId)
      
      // Validate chatId
      const chatIdNum = parseInt(chatId)
      if (isNaN(chatIdNum) || chatIdNum <= 0) {
        console.error('[ChatContext] loadChatMessages: Invalid chatId:', chatId)
        throw new Error(`Invalid chat ID: ${chatId}`)
      }
      
      // If force=true and not in sync mode, load ALL messages at once (for supervisors viewing full chat history)
      // Otherwise, use pagination
      let messages: Message[] = []
      if (force && !sinceTs && !sinceId) {
        // Load all messages in one request (chronological order, oldest first)
        console.log('[ChatContext] loadChatMessages: Loading ALL messages for chatId:', chatId, 'chatIdNum:', chatIdNum)
        messages = await getChatMessages(chatIdNum, 100, 0, undefined, undefined, undefined, undefined, true)
        if (messages.length === 0) {
          console.warn('[ChatContext] loadChatMessages: ⚠️ No messages returned for chatId:', chatId, 'This might indicate:', {
            chatId,
            chatIdNum,
            possibleIssues: [
              'Chat does not exist in database',
              'No messages exist for this chat_id',
              'Backend returned empty array',
              'Request failed silently'
            ]
          })
        } else {
          console.log('[ChatContext] loadChatMessages: ✅ Loaded', messages.length, 'total messages for chatId:', chatId)
        }
        
        // Messages are already in chronological order (oldest first) from backend
        const sortedAllMessages = messages
        
        console.log('[ChatContext] loadChatMessages: About to update chat session:', {
          chatId,
          messagesCount: sortedAllMessages.length,
          firstMessage: sortedAllMessages.length > 0 ? sortedAllMessages[0] : null,
          lastMessage: sortedAllMessages.length > 0 ? sortedAllMessages[sortedAllMessages.length - 1] : null
        })
        
        setChatSessions((prev) => {
          const chatExists = prev.some((chat) => chat.id === chatId)
          console.log('[ChatContext] loadChatMessages: Updating chat session with ALL messages:', {
            chatId,
            chatExists,
            messagesCount: sortedAllMessages.length,
            prevChatsCount: prev.length,
            existingChatMessagesCount: chatExists ? prev.find(c => c.id === chatId)?.messages?.length || 0 : 0
          })
          
          if (!chatExists) {
            const minimalChat: ChatSession = {
              id: chatId,
              clientId: '',
              operatorId: null,
              status: 'active',
              createdAt: new Date(),
              lastActivity: sortedAllMessages.length > 0 ? new Date(sortedAllMessages[sortedAllMessages.length - 1].created_at) : new Date(),
              messages: sortedAllMessages,
              lastMessage: sortedAllMessages.length > 0 ? sortedAllMessages[sortedAllMessages.length - 1] : null,
            }
            console.log('[ChatContext] loadChatMessages: Created minimal chat with', sortedAllMessages.length, 'messages')
            const newSessions = [...prev, minimalChat]
            console.log('[ChatContext] loadChatMessages: New sessions count:', newSessions.length)
            return newSessions
          }
          
          const updated = prev.map((chat) => {
            if (chat.id === chatId) {
              if (sortedAllMessages.length > 0) {
                const lastMsg = sortedAllMessages[sortedAllMessages.length - 1]
                lastMessageDataRef.current[chatId] = {
                  id: lastMsg.id,
                  ts: lastMsg.created_at
                }
              }
              
              const updatedChat = {
                ...chat,
                messages: sortedAllMessages,
                lastMessage: sortedAllMessages.length > 0 ? sortedAllMessages[sortedAllMessages.length - 1] : null,
                lastActivity: sortedAllMessages.length > 0 ? new Date(sortedAllMessages[sortedAllMessages.length - 1].created_at) : chat.lastActivity
              }
              console.log('[ChatContext] loadChatMessages: Updated existing chat with', sortedAllMessages.length, 'messages, chat.messages.length:', updatedChat.messages.length)
              return updatedChat
            }
            return chat
          })
          console.log('[ChatContext] loadChatMessages: Updated sessions count:', updated.length)
          return updated
        })
        
        loadedMessagesRef.current.add(chatId)
        loadingMessagesRef.current.delete(chatId)
        return
      } else {
        // Use pagination for sync or normal loading
        const limit = sinceTs || sinceId ? 100 : 50
        messages = await getChatMessages(chatIdNum, limit, 0, sinceTs, sinceId)
        if (messages.length === 0) {
          console.warn('[ChatContext] loadChatMessages: ⚠️ No messages returned (pagination mode) for chatId:', chatId)
        } else {
          console.log('[ChatContext] loadChatMessages: ✅ Received', messages.length, 'messages for chatId:', chatId)
        }
      }
      
      console.log('[ChatContext] loadChatMessages: Received messages:', messages.length, 'messages for chatId:', chatId)
      
      setChatSessions((prev) => {
        // Sort messages by created_at (oldest first)
        const sortedMessages = [...messages].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        )
        
        const chatExists = prev.some((chat) => chat.id === chatId)
        if (!chatExists) {
          // For clients: chat should be loaded via loadChats, but if it's not here yet,
          // we'll create a minimal chat session with messages
          // This can happen due to async state updates
          // For supervisors/operators: also create minimal chat session if chat doesn't exist
          console.log(`[ChatContext] loadChatMessages: Chat ${chatId} not in sessions yet, creating minimal session with messages for role: ${userRoleRef.current}`)
          // Create a minimal chat session - it will be updated when chat is loaded
          const minimalChat: ChatSession = {
            id: chatId,
            clientId: '', // Will be updated when chat is loaded
            operatorId: null,
            status: 'active',
            createdAt: new Date(),
            lastActivity: sortedMessages.length > 0 ? new Date(sortedMessages[sortedMessages.length - 1].created_at) : new Date(),
            messages: sortedMessages,
            lastMessage: sortedMessages.length > 0 ? sortedMessages[sortedMessages.length - 1] : null,
          }
          return [...prev, minimalChat]
        }
        
        return prev.map((chat) => {
          if (chat.id === chatId) {
            // Update last message tracking
            if (sortedMessages.length > 0) {
              const lastMsg = sortedMessages[sortedMessages.length - 1]
              lastMessageDataRef.current[chatId] = {
                id: lastMsg.id,
                ts: lastMsg.created_at
              }
            }
            
            // If syncing (since_ts/since_id), merge with existing messages
            // Otherwise, if force=true, replace all messages; if force=false, keep existing if any
            const existingMessages = chat.messages
            let finalMessages = sortedMessages
            
            console.log('[ChatContext] loadChatMessages: Updating chat session:', {
              chatId,
              existingMessagesCount: existingMessages.length,
              newMessagesCount: sortedMessages.length,
              force,
              sinceTs,
              sinceId
            })
            
            if (sinceTs || sinceId) {
              // Merge: existing + new, sort by created_at
              const merged = [...existingMessages, ...sortedMessages]
              finalMessages = merged.sort(
                (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
              )
              // Remove duplicates by ID
              const seen = new Set<number>()
              finalMessages = finalMessages.filter(m => {
                if (seen.has(m.id)) return false
                seen.add(m.id)
                return true
              })
            } else if (force) {
              // Force reload: replace all messages with new ones
              finalMessages = sortedMessages
              console.log('[ChatContext] loadChatMessages: Force reload - replacing all messages with', finalMessages.length, 'messages')
            } else if (existingMessages.length > 0) {
              // Not forcing and we have existing messages: merge to avoid duplicates
              const merged = [...existingMessages, ...sortedMessages]
              finalMessages = merged.sort(
                (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
              )
              // Remove duplicates by ID
              const seen = new Set<number>()
              finalMessages = finalMessages.filter(m => {
                if (seen.has(m.id)) return false
                seen.add(m.id)
                return true
              })
            } else {
              // No existing messages and not forcing - use new messages
              finalMessages = sortedMessages
              console.log('[ChatContext] loadChatMessages: No existing messages - using new messages:', finalMessages.length)
            }
            
            const updatedChat = {
              ...chat,
              messages: finalMessages,
              lastMessage: finalMessages.length > 0 ? finalMessages[finalMessages.length - 1] : null,
            }
            
            console.log('[ChatContext] loadChatMessages: Updated chat session:', {
              chatId,
              finalMessagesCount: updatedChat.messages.length,
              hasLastMessage: !!updatedChat.lastMessage
            })
            
            return updatedChat
          }
          return chat
        })
      })
      
      // Initialize WebSocket connection for real-time updates
      // This ensures that when a chat window is opened, WebSocket is connected
      const currentUserId = userIdRef.current
      const currentUserRole = userRoleRef.current
      console.log('[ChatContext] loadChatMessages: WebSocket check:', {
        chatId,
        currentUserId,
        currentUserRole,
        hasSubscription: subscribedChatIdsRef.current.has(chatId),
        hasInitializeFn: !!initializeWebSocketRef.current
      })
      
      // IMPORTANT: Initialize WebSocket connection AFTER messages are loaded
      // This ensures chat exists in sessions before WebSocket is created
      // We do this for ALL users (client, operator, supervisor) to ensure real-time updates
      loadedMessagesRef.current.add(chatId)
      
      // Initialize WebSocket connection for real-time updates
      // This is critical - messages must appear immediately when sent by other participants
      if (currentUserId && !subscribedChatIdsRef.current.has(chatId)) {
        // Check if WebSocket connection already exists in map (might be connecting)
        const existingWs = wsConnections.current.get(chatId)
        if (existingWs) {
          console.log('[ChatContext] loadChatMessages: WebSocket already exists in map for chat:', chatId)
          // Don't create duplicate connection, but continue with function
        } else {
          // Try to use ref first
          if (initializeWebSocketRef.current) {
            console.log('[ChatContext] loadChatMessages: Initializing WebSocket for chat:', chatId, 'userId:', currentUserId, 'role:', currentUserRole)
            initializeWebSocketRef.current(chatId, currentUserId)
          } else {
            // Fallback: add to activeChats which will call initializeWebSocket via addToActiveChats
            console.warn('[ChatContext] loadChatMessages: initializeWebSocketRef.current is null, adding to activeChats to retry')
            setActiveChats((prev) => {
              if (!prev.includes(chatId)) {
                return [...prev, chatId]
              }
              return prev
            })
          }
        }
      } else if (subscribedChatIdsRef.current.has(chatId)) {
        console.log('[ChatContext] loadChatMessages: WebSocket already subscribed for chat:', chatId)
      } else if (!currentUserId) {
        console.warn('[ChatContext] loadChatMessages: currentUserId is not available, WebSocket will not be created')
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error)
      console.error(`[ChatContext] loadChatMessages: Error loading messages for chat ${chatId}:`, {
        chatId,
        error: errorMsg,
        stack: error instanceof Error ? error.stack : undefined,
        force,
        sinceTs,
        sinceId
      })
      // Remove from loaded set on error so we can retry
      loadedMessagesRef.current.delete(chatId)
      // Don't re-throw - let the UI handle empty messages gracefully
      // But log the error clearly so it's visible in console
    } finally {
      loadingMessagesRef.current.delete(chatId)
    }
  }, []) // Stable - no dependencies to avoid infinite loops

  // Load chats from API - proper flow: GET /api/chat/list → find/create → GET /api/chat/{id}/messages → WS subscribe
  const loadChats = useCallback(async () => {
    if (!telegramId) return
    
    try {
      setIsLoading(true)
      console.log(`📥 [LOAD-CHATS-START] Fetching chats for telegram_id=${telegramId}`)
      const chats = await getChats(telegramId)
      
      console.log(`✅ [LOAD-CHATS-DONE] Received ${chats.length} chats from API:`, chats)
      
      // Convert to ChatSession format
      const sessions = chats.map(convertChatToSession)
      
      console.log('[ChatContext] loadChats: Converted sessions:', sessions.map(s => ({ id: s.id, clientId: s.clientId, status: s.status })))
      
      // Merge with existing sessions (in case minimal chat was created by loadChatMessages)
      setChatSessions((prev) => {
        const existingIds = new Set(prev.map(c => c.id))
        const newSessions = sessions.filter(s => !existingIds.has(s.id))
        const updatedSessions = prev.map(existing => {
          const updated = sessions.find(s => s.id === existing.id)
          if (updated) {
            // Merge: keep messages from existing if any, update other fields
            return {
              ...updated,
              messages: existing.messages.length > 0 ? existing.messages : updated.messages,
              lastMessage: existing.lastMessage || updated.lastMessage,
            }
          }
          return existing
        })
        return [...updatedSessions, ...newSessions]
      })
      
      // For clients: automatically load messages when chat is active
      // This ensures messages are visible when client reopens chat
      if (userRole === 'client') {
        const activeChat = sessions.find(s => s.status === 'active')
        console.log('[ChatContext] loadChats: Active chat found:', activeChat ? { id: activeChat.id, clientId: activeChat.clientId } : null, 'userId:', userId)
        if (activeChat) {
          // Load messages for active chat (initial load, limit 50)
          console.log('[ChatContext] loadChats: Loading messages for chat:', activeChat.id)
          await loadChatMessages(activeChat.id, true)
          
          // ALWAYS add to activeChats - this ensures retry mechanism can find it
          setActiveChats((prev) => {
            const updated = [...prev.filter((id) => id !== activeChat.id), activeChat.id]
            console.log('[ChatContext] loadChats: Added chat to activeChats:', updated)
            return updated
          })
          
          // Initialize WebSocket for client - this ensures real-time updates
          // IMPORTANT: userId must be available for WebSocket connection
          if (userId && !subscribedChatIdsRef.current.has(activeChat.id)) {
            console.log('[ChatContext] loadChats: userId available, initializing WebSocket for client chat:', activeChat.id, 'userId:', userId)
            initializeWebSocket(activeChat.id, userId)
          } else if (!userId) {
            console.warn('[ChatContext] loadChats: userId not available yet for client WebSocket initialization. Chat added to activeChats, will retry when userId is available.')
          } else {
            console.log('[ChatContext] loadChats: WebSocket already connected for client chat:', activeChat.id)
          }
        } else {
          console.log('[ChatContext] loadChats: No active chat found for client')
        }
      } else if (userRole === 'callcenter_operator' || userRole === 'callcenter_supervisor') {
        // For operators/supervisors: initialize WebSocket for all active chats
        // This ensures real-time updates for all chats they're viewing
        const activeSessions = sessions.filter(s => s.status === 'active')
        console.log('[ChatContext] loadChats: Initializing WebSocket for', activeSessions.length, 'active chats')
        activeSessions.forEach(session => {
          if (userId && !subscribedChatIdsRef.current.has(session.id)) {
            console.log('[ChatContext] loadChats: Initializing WebSocket for chat:', session.id)
            initializeWebSocket(session.id, userId)
          }
        })
      }
    } catch (error) {
      console.error("Error loading chats:", error)
    } finally {
      setIsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telegramId, userRole, userId]) // Depend on userId too - client needs userId for WebSocket

  // Load users (clients and operators)
  const loadUsers = useCallback(async () => {
    if (userRole === "callcenter_operator" || userRole === "callcenter_supervisor") {
      try {
        // Load both clients and operators
        const [clients, operators] = await Promise.all([
          getAvailableClients(100, 0),
          getOperators(100)
        ])
        // Combine both lists
        setUsers([...clients, ...operators])
      } catch (error) {
        console.error("Error loading users:", error)
      }
    } else if (userRole === "client") {
      // For clients: load operators so they can see operator online status
      try {
        const operators = await getOperators(100)
        setUsers(operators)
      } catch (error) {
        console.error("Error loading operators for client:", error)
      }
    }
  }, [userRole])

  // NOTE: initializeWebSocket is already defined above (line 151), duplicate removed

  // Load active chat stats - event-driven only (no polling)
  const loadActiveChatStats = useCallback(async () => {
    try {
      const stats = await getActiveChatStats()
      if (stats) {
        setActiveChatStats(stats)
      }
    } catch (error) {
      console.error("Error loading active chat stats:", error)
    }
  }, []) // Stable - no dependencies

  // Debounced refresh function - stable
  const debouncedRefresh = useCallback(() => {
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current)
    }
    
    debounceTimeoutRef.current = setTimeout(() => {
      if (telegramId) {
        loadChats()
        loadActiveChatStats()
      }
    }, cacheTimeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telegramId]) // loadChats and loadActiveChatStats are stable

  // Load chats on mount and when telegramId or userId changes - strict dependencies
  useEffect(() => {
    if (!telegramId) return
    
    console.log(`📋 [LOAD-CHATS] Loading chats... telegramId=${telegramId}, userId=${userId}`)
    loadChats()
    console.log(`📋 [LOAD-USERS] Loading users...`)
    loadUsers()
    // Stats loaded on-demand, not on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telegramId, userId]) // Depend on userId too - client needs userId for WebSocket

  // Auto-connect WebSocket for all loaded chats when app initializes
  // This ensures real-time updates are available immediately
  useEffect(() => {
    if (!userId) {
      console.warn(`⚠️ [WS-AUTO-CONNECT] No userId! Cannot connect WebSocket`)
      return
    }
    
    if (!initializeWebSocketRef.current) {
      console.warn(`⚠️ [WS-AUTO-CONNECT] initializeWebSocketRef.current is null!`)
      return
    }
    
    console.log(`🔌 [WS-AUTO-CONNECT] Checking chats... userId=${userId}, chatSessions.length=${chatSessions.length}`)
    
    if (chatSessions.length > 0) {
      console.log(`🔌 [CHAT ENTRY] Connecting to ${chatSessions.length} chat(s)...`)
    } else {
      console.warn(`⚠️ [WS-AUTO-CONNECT] No chats loaded yet! chatSessions is empty`)
    }
    
    // Connect WebSocket for each loaded chat
    chatSessions.forEach((chat) => {
      if (!subscribedChatIdsRef.current.has(chat.id)) {
        console.log(`📞 [CHAT CONNECTED] Chat ID: ${chat.id}, User: ${userId}, Status: ${chat.status}`)
        initializeWebSocketRef.current?.(chat.id, userId)
      } else {
        console.log(`ℹ️ [WS-AUTO-CONNECT] Chat ${chat.id} already subscribed`)
      }
    })
  }, [chatSessions, userId]) // Depend on chatSessions to auto-connect new chats

  // Periodic background job: Mark inactive chats (every 5 minutes)
  useEffect(() => {
    if (!telegramId) return

    // Call immediately on mount
    markInactiveChats().catch(err => {
      console.warn("Error marking inactive chats:", err)
    })

    // Then call every 5 minutes
    const interval = setInterval(() => {
      markInactiveChats().catch(err => {
        console.warn("Error marking inactive chats:", err)
      })
    }, 5 * 60 * 1000) // 5 minutes

    return () => clearInterval(interval)
  }, [telegramId])

  // REMOVED: Periodic stats refresh - now event-driven only via WebSocket
  // Stats will be updated via WebSocket events (chat.assigned, etc.)

  // Cleanup WebSocket connections on unmount
  useEffect(() => {
    return () => {
      console.log('[ChatContext] Cleaning up all WebSocket connections on unmount...')
      wsConnections.current.forEach((ws, chatId) => {
        console.log('[ChatContext] Disconnecting WebSocket for chat:', chatId)
        ws.disconnect()
      })
      wsConnections.current.clear()
      subscribedChatIdsRef.current.clear()
      console.log('[ChatContext] ✓ All WebSocket connections cleaned up')
    }
  }, [])

  const sendMessage = useCallback(async (chatId: string, message: string, senderId: number) => {
    if (!userId) return

    const messageText = message.trim()
    if (!messageText) return

    // Determine sender_type based on chat and user role
    // If sender is client, use "client", otherwise use "operator" (for both operators and supervisors)
    const chat = chatSessions.find(c => c.id === chatId)
    const senderType: "client" | "operator" | "system" = chat?.clientId === senderId.toString() ? "client" : "operator"
    
    console.log('[ChatContext] sendMessage:', {
      chatId,
      senderId,
      userId,
      clientId: chat?.clientId,
      senderType,
      userRole: userRoleRef.current
    })

    // Optimistic update - xabarni darhol ko'rsatish
    // Use negative ID to identify temporary messages (will be replaced by real message from WebSocket)
    const tempMessageId = -Date.now() // Negative ID for temp messages
    const tempMessage: Message = {
      id: tempMessageId,
      chat_id: parseInt(chatId),
      sender_id: userId,
      sender_type: senderType,
      operator_id: senderType === "operator" ? userId : null,
      sender_telegram_id: userId, // Temporary telegram ID (same as user ID)
      message_text: messageText,
      attachments: null,
      created_at: new Date().toISOString(),
      sender_name: "", // Temporary name (will be replaced by server response)
      sender_role: null,
    }

    // Darhol messages listiga qo'shish
    setChatSessions((prev) =>
      prev.map((chat) => {
        if (chat.id === chatId) {
          return {
            ...chat,
            messages: [...chat.messages, tempMessage],
            lastMessage: tempMessage,
            lastActivity: new Date(),
          }
        }
        return chat
      })
    )

    try {
      // Always use REST API to ensure message is saved to database
      // WebSocket will receive the message via real-time update and replace temp message
      // senderType is already determined above
      const messageId = await apiSendMessage(parseInt(chatId), userId, messageText, senderType)
      
      console.log('[ChatContext] sendMessage: Message sent successfully:', {
        messageId,
        chatId,
        senderType,
        userId
      })
      
      if (!messageId) {
        throw new Error("Failed to send message via REST API")
      }
      
      // WebSocket will receive the message and replace temp message
      // If WS unavailable, the optimistic update will remain until next sync
    } catch (error) {
      console.error("Error sending message:", error)
      // Xatolik bo'lsa, optimistic update ni olib tashlash
      setChatSessions((prev) =>
        prev.map((chat) => {
          if (chat.id === chatId) {
            return {
              ...chat,
              messages: chat.messages.filter((m) => m.id !== tempMessageId),
              lastMessage: chat.messages.length > 1 ? chat.messages[chat.messages.length - 2] : null,
            }
          }
          return chat
        })
      )
    }
  }, [userId, chatSessions]) // Only depend on userId and chatSessions

  const closeChat = useCallback(async (chatId: string) => {
    try {
      await apiCloseChat(parseInt(chatId))
      
      // Close WebSocket connection
      const ws = wsConnections.current.get(chatId)
      if (ws) {
        ws.disconnect()
        wsConnections.current.delete(chatId)
      }

      // Update local state - keep messages in memory so they're visible when chat is reopened
      setChatSessions((prev) =>
        prev.map((chat) => {
          if (chat.id === chatId) {
            return {
              ...chat,
              status: "inactive",
              // Keep messages - don't clear them
            }
          }
          return chat
        })
      )

      // Remove from active chats
      setActiveChats((prev) => prev.filter((id) => id !== chatId))
      
      // Clear loaded messages flag so messages will be reloaded when chat is reopened
      // This ensures fresh messages are loaded from database
      loadedMessagesRef.current.delete(chatId)
    } catch (error) {
      console.error("Error closing chat:", error)
    }
  }, []) // Stable

  const startNewChat = useCallback(async (clientId: number): Promise<string | null> => {
    if (!userId) return null

    try {
      const chat = await createChat(clientId)
      if (chat) {
        const session = convertChatToSession(chat)
        setChatSessions((prev) => [...prev, session])
        
        // Initialize WebSocket connection
        if (userId) {
          initializeWebSocket(session.id, userId)
        }
        
        // Load initial messages (force load for new chat)
        await loadChatMessages(session.id, true)
        
        return session.id
      }
      return null
    } catch (error) {
      console.error("Error creating chat:", error)
      return null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]) // initializeWebSocket and loadChatMessages are stable

  const markAsRead = useCallback((chatId: string, userId: number) => {
    setUnreadCounts((prev) => ({
      ...prev,
      [`${chatId}-${userId}`]: 0,
    }))
  }, []) // Stable

  const addToActiveChats = useCallback((chatId: string) => {
    console.log('[ChatContext] addToActiveChats: Called with chatId:', chatId, 'userId:', userId, 'userRole:', userRole, 'subscribedChats:', Array.from(subscribedChatIdsRef.current))
    // Always add to activeChats - this ensures retry mechanism can find it
    setActiveChats((prev) => {
      const updated = [...prev.filter((id) => id !== chatId), chatId]
      console.log('[ChatContext] addToActiveChats: Updated activeChats:', updated)
      return updated
    })
    
    // Initialize WebSocket if not already connected to this chat
    // Allow multiple WebSocket connections for operators (they can have multiple chats)
    // IMPORTANT: For clients, userId must be available - if not, we'll retry when userId is set
    if (userId && !subscribedChatIdsRef.current.has(chatId)) {
      console.log('[ChatContext] addToActiveChats: userId available, initializing WebSocket for chat:', chatId, 'userId:', userId, 'userRole:', userRole)
      // Use initializeWebSocket directly (not via ref) to ensure it's called
      initializeWebSocket(chatId, userId)
    } else if (!userId) {
      console.warn('[ChatContext] addToActiveChats: userId not available yet. Chat added to activeChats, will retry when userId is available. chatId:', chatId, 'userRole:', userRole)
      // Store chatId to retry WebSocket connection when userId becomes available
      // This will be handled by the useEffect that depends on userId
      // For clients, this is critical - WebSocket must be connected to receive messages
    } else {
      console.log('[ChatContext] addToActiveChats: WebSocket already connected for chat:', chatId, 'userId:', userId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, userRole, initializeWebSocket]) // Include initializeWebSocket in deps
  
  // Retry WebSocket connections when userId becomes available (for clients and operators)
  useEffect(() => {
    console.log('[ChatContext] WebSocket retry effect triggered:', { userId, userRole, telegramId, activeChatsCount: activeChats.length, chatSessionsCount: chatSessions.length })
    
    if (!userId || !userRole || !telegramId) {
      console.log('[ChatContext] WebSocket retry: userId, telegramId or userRole not available', { userId, telegramId, userRole })
      return
    }
    
    // For clients: ensure WebSocket is connected to active chat when userId becomes available
    if (userRole === 'client') {
      // Check both activeChats (chats that should have WebSocket) and chatSessions (loaded chats)
      const chatsToConnect = activeChats.filter(chatId => !subscribedChatIdsRef.current.has(chatId))
      
      console.log('[ChatContext] WebSocket retry: Checking chats', {
        activeChats,
        subscribedChats: Array.from(subscribedChatIdsRef.current),
        chatsToConnect,
        userId
      })
      
      if (chatsToConnect.length > 0) {
        console.log('[ChatContext] WebSocket retry: Found chats in activeChats that need connection:', chatsToConnect, 'userId:', userId)
        chatsToConnect.forEach(chatId => {
          console.log('[ChatContext] userId available now, initializing WebSocket for client chat:', chatId, 'userId:', userId)
          initializeWebSocket(chatId, userId)
        })
      } else {
        // Fallback: check chatSessions for active chat
        const activeChat = chatSessions.find(s => s.status === 'active')
        console.log('[ChatContext] WebSocket retry: Checking for active chat in chatSessions', { 
          activeChat: activeChat ? { id: activeChat.id, status: activeChat.status } : null,
          subscribedChats: Array.from(subscribedChatIdsRef.current),
          activeChats: activeChats,
          userId 
        })
        if (activeChat && !subscribedChatIdsRef.current.has(activeChat.id)) {
          console.log('[ChatContext] userId available now, initializing WebSocket for client chat:', activeChat.id, 'userId:', userId)
          initializeWebSocket(activeChat.id, userId)
          // Also add to activeChats to track it
          setActiveChats((prev) => [...prev.filter((id) => id !== activeChat.id), activeChat.id])
        } else if (activeChat && subscribedChatIdsRef.current.has(activeChat.id)) {
          console.log('[ChatContext] WebSocket already subscribed to chat:', activeChat.id)
        } else {
          console.log('[ChatContext] No active chat found for client WebSocket initialization')
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, telegramId, userRole, chatSessions, activeChats]) // Retry when identifiers or activeChats change

  const removeFromActiveChats = useCallback((chatId: string) => {
    setActiveChats((prev) => prev.filter((id) => id !== chatId))
    
    // Close WebSocket when chat is removed from active chats
    const ws = wsConnections.current.get(chatId)
    if (ws) {
      ws.disconnect()
      wsConnections.current.delete(chatId)
      subscribedChatIdsRef.current.delete(chatId)
    }
  }, []) // Stable

  const refreshChats = useCallback(async () => {
    // Use debounced refresh to prevent excessive API calls
    debouncedRefresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // debouncedRefresh is stable

  // Load supervisor inbox with cursor pagination
  const loadInbox = useCallback(async (limit: number = 20, cursorTs?: string, cursorId?: number) => {
    if (!telegramId || userRole !== 'callcenter_supervisor') return
    
    const cacheKey = `inbox_${limit}_${cursorTs}_${cursorId}`
    const now = Date.now()
    
    // Check cache
    if (lastFetchTime.current[cacheKey] && (now - lastFetchTime.current[cacheKey]) < cacheTimeout) {
      return // Use cached data
    }
    
    try {
      const result = await getInbox(telegramId, limit, cursorTs, cursorId)
      const sessions = result.chats.map(convertChatToSession)
      
      setChatSessions((prev) => {
        // Merge with existing chats (avoid duplicates)
        const existingIds = new Set(prev.map(c => c.id))
        const newSessions = sessions.filter(s => !existingIds.has(s.id))
        return [...prev, ...newSessions]
      })
      
      lastFetchTime.current[cacheKey] = now
    } catch (error) {
      console.error("Error loading inbox:", error)
    }
  }, [telegramId, userRole])

  // Load supervisor active chats with cursor pagination
  const loadActiveChats = useCallback(async (limit: number = 20, cursorTs?: string, cursorId?: number) => {
    if (!telegramId || userRole !== 'callcenter_supervisor') return
    
    const cacheKey = `active_chats_${limit}_${cursorTs}_${cursorId}`
    const now = Date.now()
    
    // Check cache
    if (lastFetchTime.current[cacheKey] && (now - lastFetchTime.current[cacheKey]) < cacheTimeout) {
      return // Use cached data
    }
    
    try {
      const result = await getActiveChats(telegramId, limit, cursorTs, cursorId)
      const sessions = result.chats.map(convertChatToSession)
      
      setChatSessions((prev) => {
        // Merge with existing chats (avoid duplicates)
        const existingIds = new Set(prev.map(c => c.id))
        const newSessions = sessions.filter(s => !existingIds.has(s.id))
        return [...prev, ...newSessions]
      })
      
      lastFetchTime.current[cacheKey] = now
    } catch (error) {
      console.error("Error loading active chats:", error)
    }
  }, [telegramId, userRole, convertChatToSession])

  // Load operator chats with cursor pagination
  const loadMyChats = useCallback(async (limit: number = 20, cursorTs?: string, cursorId?: number) => {
    if (!telegramId || userRole !== 'callcenter_operator') return
    
    const cacheKey = `my_chats_${limit}_${cursorTs}_${cursorId}`
    const now = Date.now()
    
    // Check cache
    if (lastFetchTime.current[cacheKey] && (now - lastFetchTime.current[cacheKey]) < cacheTimeout) {
      return // Use cached data
    }
    
    try {
      const result = await getMyChats(telegramId, limit, cursorTs, cursorId)
      const sessions = result.chats.map(convertChatToSession)
      
      setChatSessions((prev) => {
        // Merge with existing chats (avoid duplicates)
        const existingIds = new Set(prev.map(c => c.id))
        const newSessions = sessions.filter(s => !existingIds.has(s.id))
        return [...prev, ...newSessions]
      })
      
      lastFetchTime.current[cacheKey] = now
    } catch (error) {
      console.error("Error loading operator chats:", error)
    }
  }, [telegramId, userRole, convertChatToSession])
  
  // Update refs when functions change
  useEffect(() => {
    loadInboxRef.current = loadInbox
    loadActiveChatsRef.current = loadActiveChats
    loadMyChatsRef.current = loadMyChats
  }, [loadInbox, loadActiveChats, loadMyChats])

  const handleGlobalChatEvent = useCallback((event: any) => {
    if (!event || !event.type) return
    const chatIdValue = event.chat_id ?? event.chat?.id ?? event.message?.chat_id
    const chatId = typeof chatIdValue === "number" ? chatIdValue : chatIdValue ? parseInt(chatIdValue, 10) : null
    const chatIdStr = chatId ? chatId.toString() : null

    const ensureChatHydrated = (payload?: Chat | null) => {
      if (payload && payload.id) {
        upsertChatSession(payload as Chat)
        return true
      }
      if (chatId) {
        fetchChatAndUpsert(chatId)
      }
      return false
    }

    switch (event.type) {
      case "chat.new": {
        const chat = event.chat as Chat
        if (chat && chat.id) {
          // Add chat to sessions immediately
          upsertChatSession(chat)
          
          // For supervisors: refresh inbox or active chats based on operator_id
          if (userRoleRef.current === 'callcenter_supervisor') {
            if (!chat.operator_id) {
              // New chat without operator - refresh inbox
              loadInboxRef.current?.()
            } else {
              // Active chat with operator - refresh active chats
              loadActiveChatsRef.current?.()
            }
          }
          
          // For operators: refresh their chats if this chat is assigned to them
          if (userRoleRef.current === 'callcenter_operator' && chat.operator_id && chat.operator_id === userIdRef.current) {
            loadMyChatsRef.current?.()
          }
        } else if (chatId) {
          // Chat payload not provided, fetch it
          fetchChatAndUpsert(chatId)
        }
        break
      }
      case "chat.assigned": {
        const hadPayload = ensureChatHydrated(event.chat as Chat)
        if (!hadPayload && chatIdStr && event.operator_id) {
          setChatSessions((prev) => {
            let updated = false
            const next = prev.map((chat) => {
              if (chat.id === chatIdStr) {
                updated = true
                return {
                  ...chat,
                  operatorId: event.operator_id.toString(),
                }
              }
              return chat
            })
            return updated ? sortChatsByLastActivity(next) : next
          })
        }
        break
      }
      case "chat.inactive": {
        if (event.chat) {
          ensureChatHydrated(event.chat as Chat)
          break
        }
        if (!chatIdStr) break
        setChatSessions((prev) => {
          let updated = false
          const next = prev.map((chat) => {
            if (chat.id === chatIdStr) {
              updated = true
              return {
                ...chat,
                status: "inactive" as "inactive",
                operatorId: null,
              }
            }
            return chat
          })
          return updated ? sortChatsByLastActivity(next) : next
        })
        break
      }
      case "chat.message": {
        if (!chatIdStr || !event.message) {
          ensureChatHydrated(event.chat as Chat)
          break
        }
        const message = event.message as Message
        const activityDate = message.created_at ? new Date(message.created_at) : new Date()
        setChatSessions((prev) => {
          const index = prev.findIndex((chat) => chat.id === chatIdStr)
          if (index === -1) {
            if (chatId) {
              fetchChatAndUpsert(chatId)
            }
            return prev
          }
          const existingChat = prev[index]
          // Check if message already exists (avoid duplicates)
          const messageExists = existingChat.messages.some(m => m.id === message.id)
          
          // Also check for temporary message (negative ID) that should be replaced
          const tempMessageIndex = existingChat.messages.findIndex((m) => 
            m.id < 0 && // Temporary message has negative ID
            m.message_text === message.message_text && 
            Math.abs(new Date(m.created_at).getTime() - new Date(message.created_at).getTime()) < 10000) // Within 10 seconds
          
          let updatedMessages: Message[]
          if (messageExists) {
            // Message already exists - update it with latest data
            updatedMessages = existingChat.messages.map(m => m.id === message.id ? message : m)
          } else if (tempMessageIndex >= 0) {
            // Replace temporary message with real one
            updatedMessages = [...existingChat.messages]
            updatedMessages[tempMessageIndex] = message
          } else {
            // Completely new message - add it
            updatedMessages = [...existingChat.messages, message]
          }
          
          // Sort messages by created_at
          updatedMessages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
          
          const updatedChat = {
            ...existingChat,
            messages: updatedMessages,
            lastActivity: activityDate,
            lastMessage: message,
          }
          const next = [...prev]
          next[index] = updatedChat
          return sortChatsByLastActivity(next)
        })
        
        // Trigger auto-open callback if set
        if (onNewMessageRef.current && chatIdStr) {
          onNewMessageRef.current(chatIdStr)
        }
        break
      }
      default:
        break
    }
  }, [fetchChatAndUpsert, upsertChatSession])

  // Initialize StatsWebSocket for operators and supervisors (online status tracking)
  useEffect(() => {
    if (!userId || !userRole) return
    if (userRole !== 'callcenter_operator' && userRole !== 'callcenter_supervisor') return
    
    const statsWs = new StatsWebSocket(
      userId,
      (stats) => {
        // Update stats
        setActiveChatStats(stats)
      },
      (userId, role) => {
        // User came online
        setOnlineUsers(prev => new Set([...prev, userId]))
      },
      (userId, role) => {
        // User went offline
        setOnlineUsers(prev => {
          const updated = new Set(prev)
          updated.delete(userId)
          return updated
        })
      },
      (event) => {
        handleGlobalChatEvent(event)
      }
    )
    
    statsWs.connect()
    statsWsRef.current = statsWs
    
    return () => {
      if (statsWsRef.current) {
        statsWsRef.current.disconnect()
        statsWsRef.current = null
      }
    }
  }, [userId, userRole, handleGlobalChatEvent])

  // Load staff chats
  const loadStaffChats = useCallback(async () => {
    if (!telegramId || !userRole) return
    if (userRole !== 'callcenter_operator' && userRole !== 'callcenter_supervisor') return
    
    try {
      console.log('[ChatContext] loadStaffChats: Loading staff chats for telegramId:', telegramId)
      const result = await getStaffChats(telegramId) as { chats: StaffChat[] }
      console.log('[ChatContext] loadStaffChats: Received', result.chats.length, 'staff chats')
      
      // First, create sessions without messages (fast)
      const sessions = result.chats.map((chat: StaffChat) => {
        // Convert staff chat to ChatSession format
        // For staff chats: sender_id and receiver_id are used instead of client_id and operator_id
        const currentUserId = userId || 0
        const otherUserId = chat.sender_id === currentUserId ? chat.receiver_id : chat.sender_id
        
        return {
          id: chat.id.toString(),
          clientId: chat.sender_id?.toString() || '',
          operatorId: chat.receiver_id?.toString() || null,
          status: chat.status,
          createdAt: new Date(chat.created_at),
          lastActivity: new Date(chat.last_activity_at || chat.updated_at),
          messages: [],
          lastMessage: null, // Will be loaded separately
          clientName: chat.sender_name,
          operatorName: chat.receiver_name,
        }
      })
      
      console.log('[ChatContext] loadStaffChats: Created', sessions.length, 'staff chat sessions')
      setStaffChats(sessions)
      
      // Then, load last messages for each chat in parallel (non-blocking)
      // This doesn't block the UI and happens in background
      Promise.all(sessions.map(async (session) => {
        try {
          const messages = await getStaffChatMessages(parseInt(session.id), telegramId, 1, 0)
          if (messages.length > 0) {
            // Get the last message (most recent)
            const sortedMessages = [...messages].sort(
              (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            )
            const lastMessage = sortedMessages[0]
            
            // Update the session with lastMessage
            setStaffChats((prev) => 
              prev.map((chat) => 
                chat.id === session.id 
                  ? { ...chat, lastMessage }
                  : chat
              )
            )
            
            console.log(`[ChatContext] loadStaffChats: Updated lastMessage for staff chat ${session.id}`)
          }
        } catch (error) {
          console.error(`[ChatContext] loadStaffChats: Error loading lastMessage for staff chat ${session.id}:`, error)
          // Continue without lastMessage - will load when chat is opened
        }
      })).catch((error) => {
        console.error('[ChatContext] loadStaffChats: Error loading lastMessages:', error)
        // Don't throw - sessions are already set, just lastMessages failed
      })
      
    } catch (error) {
      console.error("[ChatContext] loadStaffChats: Error loading staff chats:", error)
      // Set empty array on error to prevent blocking
      setStaffChats([])
    }
  }, [telegramId, userRole, userId])

  // Start staff chat
  const startStaffChat = useCallback(async (receiverId: number): Promise<string | null> => {
    if (!userId || !telegramId) {
      console.error('[ChatContext] startStaffChat: userId or telegramId not available', { userId, telegramId })
      return null
    }

    try {
      const chat = await createStaffChat(userId, receiverId, telegramId) as StaffChat
      if (chat) {
        const session: ChatSession = {
          id: chat.id.toString(),
          clientId: chat.sender_id?.toString() || '',
          operatorId: chat.receiver_id?.toString() || null,
          status: chat.status,
          createdAt: new Date(chat.created_at),
          lastActivity: new Date(chat.last_activity_at || chat.updated_at),
          messages: [],
          lastMessage: null,
          clientName: chat.sender_name,
          operatorName: chat.receiver_name,
        }
        
        setStaffChats((prev) => {
          const existingIds = new Set(prev.map(c => c.id))
          if (existingIds.has(session.id)) {
            return prev.map(c => c.id === session.id ? session : c)
          }
          return [...prev, session]
        })
        
        // Initialize WebSocket connection
        if (userId) {
          initializeStaffWebSocket(session.id, userId)
        }
        
        // Load initial messages
        await loadStaffChatMessages(session.id, true)
        
        return session.id
      }
      return null
    } catch (error) {
      console.error("Error creating staff chat:", error)
      return null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]) // initializeStaffWebSocket and loadStaffChatMessages are stable

  // Load staff chat messages
  const loadStaffChatMessages = useCallback(async (chatId: string, force: boolean = false) => {
    if (!telegramId) return
    
    if (!force && loadedMessagesRef.current.has(`staff_${chatId}`)) {
      console.log(`[ChatContext] loadStaffChatMessages: Skipping ${chatId} (already loaded, force=${force})`)
      return
    }
    
    loadingMessagesRef.current.add(`staff_${chatId}`)
    
    try {
      console.log(`[ChatContext] loadStaffChatMessages: Loading messages for staff chat ${chatId}, force=${force}`)
      
      // Check if chat exists in staffChats before loading messages
      let chatExists = false
      let existingChat: ChatSession | null = null
      setStaffChats((prev) => {
        chatExists = prev.some((chat) => chat.id === chatId)
        existingChat = prev.find((chat) => chat.id === chatId) || null
        return prev
      })
      
      // If chat doesn't exist, try to load it first
      let staffChat: StaffChat | null = null
      if (!chatExists) {
        console.log(`[ChatContext] loadStaffChatMessages: Staff chat ${chatId} not found in sessions, loading chat details first`)
        try {
          staffChat = await getStaffChat(parseInt(chatId), telegramId)
          if (staffChat) {
            console.log(`[ChatContext] loadStaffChatMessages: Loaded staff chat ${chatId} details`)
          }
        } catch (error) {
          console.error(`[ChatContext] loadStaffChatMessages: Error loading staff chat ${chatId}:`, error)
        }
      }
      
      const messages = await getStaffChatMessages(parseInt(chatId), telegramId, 200, 0) // Increased limit to 200
      console.log(`[ChatContext] loadStaffChatMessages: Received ${messages.length} messages for staff chat ${chatId}`)
      
      setStaffChats((prev) => {
        const sortedMessages = [...messages].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        )
        
        const chatExistsNow = prev.some((chat) => chat.id === chatId)
        if (!chatExistsNow) {
          // Chat doesn't exist - create session with loaded chat details or minimal
          if (staffChat) {
            const currentUserId = userIdRef.current || 0
            const session: ChatSession = {
              id: staffChat.id.toString(),
              clientId: staffChat.sender_id?.toString() || '',
              operatorId: staffChat.receiver_id?.toString() || null,
              status: staffChat.status,
              createdAt: new Date(staffChat.created_at),
              lastActivity: new Date(staffChat.last_activity_at || staffChat.updated_at),
              messages: sortedMessages,
              lastMessage: sortedMessages.length > 0 ? sortedMessages[sortedMessages.length - 1] : null,
              clientName: staffChat.sender_name,
              operatorName: staffChat.receiver_name,
            }
            console.log(`[ChatContext] loadStaffChatMessages: Created staff chat session with ${sortedMessages.length} messages`)
            return [...prev, session]
          } else {
            // Fallback: create minimal chat session if chat loading fails
            console.log(`[ChatContext] loadStaffChatMessages: Creating minimal staff chat session with ${sortedMessages.length} messages`)
            const minimalChat: ChatSession = {
              id: chatId,
              clientId: '', // Will be updated when chat is loaded
              operatorId: null,
              status: 'active',
              createdAt: new Date(),
              lastActivity: sortedMessages.length > 0 ? new Date(sortedMessages[sortedMessages.length - 1].created_at) : new Date(),
              messages: sortedMessages,
              lastMessage: sortedMessages.length > 0 ? sortedMessages[sortedMessages.length - 1] : null,
            }
            return [...prev, minimalChat]
          }
        }
        
        return prev.map((chat) => {
          if (chat.id === chatId) {
            // If force=true, replace all messages; otherwise merge
            const existingMessages = chat.messages
            let finalMessages = sortedMessages
            if (force) {
              // Force reload: replace all messages with new ones
              finalMessages = sortedMessages
              console.log(`[ChatContext] loadStaffChatMessages: Force reload - replacing all messages with ${finalMessages.length} messages`)
            } else if (existingMessages.length > 0) {
              // Merge to avoid duplicates
              const merged = [...existingMessages, ...sortedMessages]
              finalMessages = merged.sort(
                (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
              )
              // Remove duplicates by ID
              const seen = new Set<number>()
              finalMessages = finalMessages.filter(m => {
                if (seen.has(m.id)) return false
                seen.add(m.id)
                return true
              })
            }
            
            const updatedChat = {
              ...chat,
              messages: finalMessages,
              lastMessage: finalMessages.length > 0 ? finalMessages[finalMessages.length - 1] : null,
            }
            
            console.log(`[ChatContext] loadStaffChatMessages: Updated staff chat ${chatId} with ${finalMessages.length} messages`)
            return updatedChat
          }
          return chat
        })
      })
      
      loadedMessagesRef.current.add(`staff_${chatId}`)
    } catch (error) {
      console.error(`Error loading staff chat messages for ${chatId}:`, error)
      // Remove from loaded set on error so we can retry
      loadedMessagesRef.current.delete(`staff_${chatId}`)
    } finally {
      loadingMessagesRef.current.delete(`staff_${chatId}`)
    }
  }, [telegramId])

  // Initialize staff chat WebSocket
  const initializeStaffWebSocket = useCallback((chatId: string, userId: number) => {
    if (typeof window === 'undefined' || !window.WebSocket) {
      return
    }
    
    if (!userId || userId <= 0) {
      return
    }
    
    const existing = staffWsConnections.current.get(chatId)
    if (existing) {
      existing.disconnect()
      staffWsConnections.current.delete(chatId)
    }

    try {
      const ws = new StaffChatWebSocket(
        parseInt(chatId),
        userId,
        (message: Message) => {
          const messageChatId = message.chat_id.toString()
          
          setStaffChats((prev) => {
            const chatIndex = prev.findIndex((chat) => chat.id === messageChatId)
            
            if (chatIndex >= 0) {
              const chat = prev[chatIndex]
              const existingIndex = chat.messages.findIndex((m) => m.id === message.id)
              
              if (existingIndex >= 0) {
                const updatedMessages = [...chat.messages]
                updatedMessages[existingIndex] = message
                
                const updated = [...prev]
                updated[chatIndex] = {
                  ...chat,
                  messages: updatedMessages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
                  lastMessage: message,
                  lastActivity: new Date(message.created_at),
                }
                return updated
              } else {
                const updated = [...prev]
                updated[chatIndex] = {
                  ...chat,
                  messages: [...chat.messages, message].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
                  lastMessage: message,
                  lastActivity: new Date(message.created_at),
                }
                
                // Auto-open chat window if callback is set (for operators/supervisors)
                if (onNewMessageRef.current) {
                  onNewMessageRef.current(messageChatId)
                }
                
                return updated
              }
            }
            return prev
          })
        },
        (userId: number, isTyping: boolean) => {
          setTypingUsers((prev) => ({
            ...prev,
            [`staff_${chatId}-${userId}`]: isTyping,
          }))
        },
        (error: Error) => {
          console.warn(`Staff chat WebSocket error for chat ${chatId}:`, error)
        }
      )

      ws.connect()
      staffWsConnections.current.set(chatId, ws)
    } catch (error) {
      console.warn(`Failed to initialize staff chat WebSocket for chat ${chatId}:`, error)
    }
  }, [])

  // Send staff message
  const sendStaffMessage = useCallback(async (chatId: string, message: string, senderId: number) => {
    if (!userId || !telegramId) return

    const messageText = message.trim()
    if (!messageText) return

    // Optimistic update
    const tempMessageId = -Date.now()
    const tempMessage: Message = {
      id: tempMessageId,
      chat_id: parseInt(chatId),
      sender_id: userId,
      sender_type: 'operator',
      operator_id: userId,
      sender_telegram_id: userId,
      message_text: messageText,
      attachments: null,
      created_at: new Date().toISOString(),
      sender_name: "",
      sender_role: null,
    }

    setStaffChats((prev) =>
      prev.map((chat) => {
        if (chat.id === chatId) {
          return {
            ...chat,
            messages: [...chat.messages, tempMessage],
            lastMessage: tempMessage,
            lastActivity: new Date(),
          }
        }
        return chat
      })
    )

    try {
      // Use API function directly (imported as apiSendStaffMessage from api)
      const messageId = await apiSendStaffMessage(parseInt(chatId), senderId, messageText, telegramId)
      
      if (!messageId) {
        throw new Error("Failed to send staff message")
      }
    } catch (error) {
      console.error("Error sending staff message:", error)
      setStaffChats((prev) =>
        prev.map((chat) => {
          if (chat.id === chatId) {
            return {
              ...chat,
              messages: chat.messages.filter((m) => m.id !== tempMessageId),
              lastMessage: chat.messages.length > 1 ? chat.messages[chat.messages.length - 2] : null,
            }
          }
          return chat
        })
      )
    }
  }, [userId, telegramId])

  // Set callback for auto-opening chat when new message arrives
  const setOnNewMessage = useCallback((callback: ((chatId: string) => void) | null) => {
    onNewMessageRef.current = callback
  }, [])

  // Cleanup WebSocket connections on unmount
  useEffect(() => {
    return () => {
      wsConnections.current.forEach((ws) => ws.disconnect())
      wsConnections.current.clear()
      staffWsConnections.current.forEach((ws) => ws.disconnect())
      staffWsConnections.current.clear()
      if (statsWsRef.current) {
        statsWsRef.current.disconnect()
        statsWsRef.current = null
      }
    }
  }, [])

  return (
    <ChatContext.Provider
      value={{
        chatSessions,
        staffChats,
        users,
        activeChats,
        typingUsers,
        unreadCounts,
        isLoading,
        activeChatStats,
        onlineUsers,
        sendMessage,
        closeChat,
        startNewChat,
        markAsRead,
        addToActiveChats,
        removeFromActiveChats,
        refreshChats,
        loadChats,
        loadChatMessages,
        loadInbox,
        loadActiveChats,
        loadMyChats,
        loadActiveChatStats,
        loadStaffChats,
        startStaffChat,
        sendStaffMessage,
        loadStaffChatMessages,
        setOnNewMessage,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export const useChat = () => {
  const context = useContext(ChatContext)
  if (!context) {
    throw new Error("useChat must be used within ChatProvider")
  }
  return context
}

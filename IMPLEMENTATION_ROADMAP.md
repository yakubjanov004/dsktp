# Telegram Clone Funksiyalarni Qo'shish - Batafsil Reja

## Kirish

Bu hujjat loyihangizga Telegram clone funksiyalarini qo'shish uchun ketma-ketlik rejasini o'z ichiga oladi. Har bir bob alohida implementatsiya qilinadi va to'liq yakunlangandan keyin keyingi bobga o'tiladi.

---

## BOB 1: Typing Indicators (Yozish Ko'rsatkichlari)

### Maqsad
Foydalanuvchi yozayotganda boshqa foydalanuvchiga real-time ko'rsatkich ko'rsatish.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Frontend UI komponenti va WebSocket event handling
- **pasonk/ai-chatkit** - Backend WebSocket typing event patterns

### Olinadigan Qismlar

#### Backend (FastAPI)
**Manba**: `pasonk/ai-chatkit` yoki o'xshash loyihalar
- **Fayl**: `alfaconnect/api/routes/websocket.py`
- **Qo'shiladigan kod**:
  - Typing status tracking dictionary: `{chat_id: {user_id: timestamp}}`
  - Typing event broadcast funksiyasi
  - Typing timeout handler (3-5 soniyadan keyin avtomatik o'chirish)
  - WebSocket endpoint: `/ws/chat/{chat_id}/typing` yoki mavjud endpointga typing event qo'shish

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/ChatWindow.tsx`
- **Qo'shiladigan kod**:
  - Typing indicator UI komponenti (3 nuqta animatsiyasi)
  - InputBar'da typing event yuborish (onChange handler)
  - ChatContext'da typingUsers state management
  - WebSocket'da typing event listener

#### Database
- **O'zgartirish kerak emas** - Real-time event sifatida ishlaydi

### Implementatsiya Ketma-ketligi
1. Backend WebSocket typing event qo'shish
2. Frontend typing event yuborish
3. Frontend typing indicator UI komponenti
4. Typing timeout logikasi
5. Testing va optimization

### Kutilayotgan Natija
Foydalanuvchi yozayotganda, boshqa foydalanuvchi chat oynasida "Foydalanuvchi yozmoqda..." ko'rsatkichini ko'radi.

---

## BOB 2: Message Reactions (Xabar Reaksiyalari)

### Maqsad
Xabarlarga emoji reaksiyalar qo'shish (👍, ❤️, 😂, va h.k.)

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Reaction UI komponenti va emoji picker
- **AdekolaThanni/Telegram-Clone** - Reaction data structure va backend patterns

### Olinadigan Qismlar

#### Database Schema
**Manba**: Telegram clone loyihalarining database strukturasidan
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan jadval**: `message_reactions`
  - `id` (primary key)
  - `message_id` (foreign key to messages)
  - `user_id` (foreign key to users)
  - `emoji` (varchar, emoji kod)
  - `created_at` (timestamp)

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone` yoki o'xshash
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpointlar**:
  - `POST /chat/{chat_id}/messages/{message_id}/reactions` - Reaction qo'shish/o'chirish
  - `GET /chat/{chat_id}/messages/{message_id}/reactions` - Reactionlar ro'yxati
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiyalar**:
  - `add_message_reaction(message_id, user_id, emoji)`
  - `remove_message_reaction(message_id, user_id, emoji)`
  - `get_message_reactions(message_id)`

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/MessageBubble.tsx`
- **Qo'shiladigan kod**:
  - Reaction emojilar ko'rsatish (message ostida)
  - Reaction qo'shish/o'chirish onClick handler
  - Reaction picker modal (emoji tanlash)
- **Fayl**: `webapp/app/components/shared/ReactionPicker.tsx` (yangi)
- **Qo'shiladigan kod**:
  - Emoji grid UI
  - Reaction selection handler
  - Popular emojilar ro'yxati

#### WebSocket Events
- **Fayl**: `alfaconnect/api/routes/websocket.py`
- **Qo'shiladigan event**: `message.reaction` - Reaction qo'shilganda/o'chirilganda broadcast

### Implementatsiya Ketma-ketligi
1. Database migration yaratish
2. Backend database queries
3. Backend API endpoints
4. WebSocket reaction events
5. Frontend ReactionPicker komponenti
6. Frontend MessageBubble'ga reaction UI qo'shish
7. Testing va optimization

### Kutilayotgan Natija
Har bir xabarga emoji reaksiya qo'shish/o'chirish mumkin, reactionlar real-time yangilanadi.

---

## BOB 3: Message Search (Xabar Qidiruv)

### Maqsad
Chat ichida xabarlarni qidirish funksiyasi.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Search UI komponenti
- **AdekolaThanni/Telegram-Clone** - Full-text search implementation

### Olinadigan Qismlar

#### Database
**Manba**: PostgreSQL full-text search patterns
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan**:
  - `messages` jadvaliga full-text search index qo'shish
  - `tsvector` column yoki `GIN` index

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone` yoki PostgreSQL full-text search examples
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpoint**:
  - `GET /chat/{chat_id}/search?query=...&limit=50` - Xabarlarni qidirish
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiya**:
  - `search_messages(chat_id, query, limit)` - PostgreSQL `to_tsvector` va `ts_query` ishlatadi

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/ChatWindow.tsx`
- **Qo'shiladigan kod**:
  - Search input field (chat header yoki alohida modal)
  - Search results ko'rsatish
  - Search highlight (qidirilgan so'zni belgilash)
  - Search resultga click qilganda xabarga scroll qilish
- **Fayl**: `webapp/app/components/shared/ChatSearch.tsx` (yangi)
- **Qo'shiladigan kod**:
  - Search modal UI
  - Search input va results list
  - Highlight matches funksiyasi

### Implementatsiya Ketma-ketligi
1. Database full-text search index qo'shish
2. Backend search query funksiyasi
3. Backend search API endpoint
4. Frontend search modal komponenti
5. Frontend search results UI
6. Search highlight funksiyasi
7. Search resultga scroll qilish
8. Testing va optimization

### Kutilayotgan Natija
Chat ichida xabarlarni qidirish mumkin, natijalar highlight qilinadi va click qilganda xabarga scroll qilinadi.

---

## BOB 4: Message Forwarding (Xabar Forward Qilish)

### Maqsad
Xabarni boshqa chatga forward qilish funksiyasi.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Forward UI va chat selection
- **AdekolaThanni/Telegram-Clone** - Forward message data structure

### Olinadigan Qismlar

#### Database Schema
**Manba**: Telegram clone loyihalaridan
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan**:
  - `messages` jadvaliga `forwarded_from_message_id` (nullable foreign key)
  - `forwarded_from_chat_id` (nullable)
  - `forwarded_from_user_id` (nullable)

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpoint**:
  - `POST /chat/{chat_id}/messages/{message_id}/forward` - Xabarni forward qilish
  - Request body: `{target_chat_id: int}`
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiya**:
  - `forward_message(message_id, target_chat_id, sender_id)` - Original xabarni copy qiladi va metadata bilan saqlaydi

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/MessageBubble.tsx`
- **Qo'shiladigan kod**:
  - Message context menu (right-click yoki long-press)
  - "Forward" option
  - Forwarded message indicator UI ("Forwarded from...")
- **Fayl**: `webapp/app/components/shared/ForwardModal.tsx` (yangi)
- **Qo'shiladigan kod**:
  - Chat list (forward qilish uchun chat tanlash)
  - Forward preview (xabar ko'rinishi)
  - Forward button

#### WebSocket Events
- **Fayl**: `alfaconnect/api/routes/websocket.py`
- **Qo'shiladigan event**: `message.forwarded` - Forward qilingan xabar yangi chatda ko'rsatiladi

### Implementatsiya Ketma-ketligi
1. Database schema o'zgartirish
2. Backend forward message funksiyasi
3. Backend forward API endpoint
4. Frontend message context menu
5. Frontend ForwardModal komponenti
6. Frontend forwarded message indicator
7. WebSocket forward events
8. Testing va optimization

### Kutilayotgan Natija
Xabarni tanlab, boshqa chatga forward qilish mumkin, forwarded xabar "Forwarded from..." ko'rsatkichiga ega.

---

## BOB 5: Voice Messages (Ovozli Xabarlar)

### Maqsad
Ovozli xabar yozish va yuborish funksiyasi.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Audio recorder UI va player
- **AdekolaThanni/Telegram-Clone** - Audio file handling va storage

### Olinadigan Qismlar

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpoint**:
  - `POST /chat/{chat_id}/messages/voice` - Audio file upload (multipart/form-data)
  - Audio file validation (format, size limit)
- **Fayl**: `alfaconnect/utils/audio_handler.py` (yangi)
- **Qo'shiladigan kod**:
  - Audio file validation
  - Audio file storage (local yoki cloud)
  - Audio metadata extraction (duration, format)

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/InputBar.tsx`
- **Qo'shiladigan kod**:
  - Voice record button (microphone icon)
  - Audio recording state management
  - MediaRecorder API integration
- **Fayl**: `webapp/app/components/shared/VoiceMessage.tsx` (yangi)
- **Qo'shiladigan kod**:
  - Audio player UI (play/pause button)
  - Waveform visualization (optional)
  - Duration display
  - Audio playback controls

#### Database
- **O'zgartirish kerak emas** - `attachments` JSONB field'da audio file URL va metadata saqlanadi

#### File Storage
- **Manba**: Telegram clone loyihalaridan
- **Qo'shiladigan**:
  - Audio file storage path: `media/voice/{chat_id}/{message_id}.{format}`
  - Audio file size limit: 20MB
  - Supported formats: MP3, OGG, WAV

### Implementatsiya Ketma-ketligi
1. Backend audio file upload endpoint
2. Backend audio file validation va storage
3. Frontend audio recorder (MediaRecorder API)
4. Frontend VoiceMessage player komponenti
5. Frontend InputBar'ga voice button qo'shish
6. Audio file upload progress
7. Testing va optimization

### Kutilayotgan Natija
Microphone button bosilganda audio yoziladi, yuboriladi va chatda audio player ko'rsatiladi.

---

## BOB 6: Media Gallery (Media Galereya)

### Maqsad
Chat ichida barcha media fayllarni (rasm, video) galereya ko'rinishida ko'rsatish.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Media gallery UI va carousel
- **AdekolaThanni/Telegram-Clone** - Media file listing va preview

### Olinadigan Qismlar

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpoint**:
  - `GET /chat/{chat_id}/media?type=image|video&limit=50` - Media fayllar ro'yxati
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiya**:
  - `get_chat_media(chat_id, media_type, limit)` - Attachments'da image/video bo'lgan xabarlarni qaytaradi

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/ChatWindow.tsx`
- **Qo'shiladigan kod**:
  - Media gallery button (chat header yoki menu)
  - Media gallery modal ochish
- **Fayl**: `webapp/app/components/shared/MediaGallery.tsx` (yangi)
- **Qo'shiladigan kod**:
  - Media grid layout (rasmlar/videolar)
  - Image/video preview modal
  - Full-screen viewer
  - Media carousel (swipe navigation)
  - Media type filter (images/videos/all)

### Implementatsiya Ketma-ketlik
1. Backend media listing endpoint
2. Backend media query funksiyasi
3. Frontend MediaGallery komponenti
4. Frontend media grid UI
5. Frontend image/video preview
6. Frontend full-screen viewer
7. Frontend carousel navigation
8. Testing va optimization

### Kutilayotgan Natija
Chat header'da media gallery button, bosilganda barcha rasm/videolar grid ko'rinishida, click qilganda full-screen preview.

---

## BOB 7: Message Editing (Xabarni Tahrirlash)

### Maqsad
Yuborilgan xabarni tahrirlash funksiyasi.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Edit message UI va inline editing
- **AdekolaThanni/Telegram-Clone** - Edit message data structure

### Olinadigan Qismlar

#### Database Schema
**Manba**: Telegram clone loyihalaridan
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan**:
  - `messages` jadvaliga `edited_at` (nullable timestamp)
  - `edit_history` (JSONB, optional - edit tarixi)
  - Constraint: faqat 15 daqiqadan keyin edit qilish mumkin (optional)

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpoint**:
  - `PUT /chat/{chat_id}/messages/{message_id}` - Xabarni tahrirlash
  - Request body: `{message_text: string}`
  - Validation: faqat xabar egasi edit qila oladi, 15 daqiqadan keyin edit qilish mumkin emas
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiya**:
  - `edit_message(message_id, new_text, user_id)` - Xabarni yangilaydi va edited_at ni set qiladi

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/MessageBubble.tsx`
- **Qo'shiladigan kod**:
  - "Edited" label ko'rsatish (edited_at bo'lsa)
  - Message context menu'da "Edit" option
  - Inline editing mode (xabar o'rniga input field)
- **Fayl**: `webapp/app/components/shared/EditMessageInput.tsx` (yangi, optional)
- **Qo'shiladigan kod**:
  - Edit input field
  - Save/Cancel buttons

#### WebSocket Events
- **Fayl**: `alfaconnect/api/routes/websocket.py`
- **Qo'shiladigan event**: `message.edited` - Xabar tahrirlanganda broadcast

### Implementatsiya Ketma-ketligi
1. Database schema o'zgartirish
2. Backend edit message funksiyasi
3. Backend edit API endpoint
4. Frontend message context menu
5. Frontend inline editing UI
6. Frontend "Edited" label
7. WebSocket edit events
8. Testing va optimization

### Kutilayotgan Natija
O'z xabarini tahrirlash mumkin, tahrirlangan xabar "Edited" labeliga ega bo'ladi.

---

## BOB 8: Chat Pinning (Chatni Pin Qilish)

### Maqsad
Muhim chatlarni pin qilish va pinlangan chatlar ro'yxatini ko'rsatish.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Pinned chats UI va pin/unpin actions
- **AdekolaThanni/Telegram-Clone** - Pin data structure

### Olinadigan Qismlar

#### Database Schema
**Manba**: Telegram clone loyihalaridan
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan jadval**: `pinned_chats`
  - `id` (primary key)
  - `user_id` (foreign key to users)
  - `chat_id` (foreign key to chats)
  - `pinned_at` (timestamp)
  - `position` (integer, sort order)
  - Unique constraint: (user_id, chat_id)

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpointlar**:
  - `POST /chat/{chat_id}/pin` - Chatni pin qilish
  - `DELETE /chat/{chat_id}/pin` - Chatni unpin qilish
  - `GET /chat/pinned` - Pinlangan chatlar ro'yxati
- **Fayl**: `alfaconnect/database/webapp/chat_queries.py`
- **Qo'shiladigan funksiyalar**:
  - `pin_chat(user_id, chat_id)`
  - `unpin_chat(user_id, chat_id)`
  - `get_pinned_chats(user_id)`

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/ChatList.tsx`
- **Qo'shiladigan kod**:
  - Pinned chats section (yuqorida)
  - Pin icon ko'rsatish
  - Pin/unpin button
- **Fayl**: `webapp/app/components/shared/ChatHeader.tsx`
- **Qo'shiladigan kod**:
  - Pin/unpin button (chat menu yoki header'da)

### Implementatsiya Ketma-ketligi
1. Database schema o'zgartirish
2. Backend pin/unpin funksiyalari
3. Backend pinned chats API endpoints
4. Frontend pinned chats section
5. Frontend pin/unpin UI
6. Frontend pin icon va indicators
7. Testing va optimization

### Kutilayotgan Natija
Chatlarni pin qilish mumkin, pinlangan chatlar ro'yxatning yuqorisida ko'rsatiladi.

---

## BOB 9: Read Receipts Yaxshilash (O'qilgan Xabarlar)

### Maqsad
Xabarlarning o'qilgan holatini batafsil ko'rsatish (sent, delivered, read, read by list).

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Read receipt UI va status indicators
- **AdekolaThanni/Telegram-Clone** - Read receipt tracking patterns

### Olinadigan Qismlar

#### Database Schema
**Manba**: Telegram clone loyihalaridan
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan jadval**: `message_reads`
  - `id` (primary key)
  - `message_id` (foreign key to messages)
  - `user_id` (foreign key to users)
  - `read_at` (timestamp)
  - Unique constraint: (message_id, user_id)

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpointlar**:
  - `POST /chat/{chat_id}/messages/{message_id}/read` - Xabarni o'qilgan deb belgilash
  - `GET /chat/{chat_id}/messages/{message_id}/reads` - Xabarni kimlar o'qigan ro'yxati
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiyalar**:
  - `mark_message_read(message_id, user_id)`
  - `get_message_reads(message_id)`
  - `get_unread_messages_count(chat_id, user_id)` - Yaxshilash

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/MessageBubble.tsx`
- **Qo'shiladigan kod**:
  - Read receipt icons (single check, double check, blue check)
  - Read by list (hover yoki click)
  - Read timestamp ko'rsatish
- **Fayl**: `webapp/app/context/ChatContext.tsx`
- **Qo'shiladigan kod**:
  - Message read tracking (xabar ko'rinishida avtomatik read qilish)
  - Read status state management

#### WebSocket Events
- **Fayl**: `alfaconnect/api/routes/websocket.py`
- **Qo'shiladigan event**: `message.read` - Xabar o'qilganda broadcast

### Implementatsiya Ketma-ketligi
1. Database schema o'zgartirish
2. Backend read tracking funksiyalari
3. Backend read API endpoints
4. Frontend read receipt icons
5. Frontend read by list UI
6. Frontend auto-read tracking (intersection observer)
7. WebSocket read events
8. Testing va optimization

### Kutilayotgan Natija
Xabarlar o'qilganda status yangilanadi, read receipt iconlar ko'rsatiladi, read by list ko'rsatiladi.

---

## BOB 10: Message Threading (Xabar Threading)

### Maqsad
Xabarga javob berish va thread ko'rinishida ko'rsatish.

### Qaysi Repositorydan Olinadi
- **samarbadriddin0v/telegram-clone** - Reply UI va thread view
- **AdekolaThanni/Telegram-Clone** - Thread data structure

### Olinadigan Qismlar

#### Database Schema
**Manba**: Telegram clone loyihalaridan
- **Fayl**: `alfaconnect/database/migrations/` - yangi migration
- **Qo'shiladigan**:
  - `messages` jadvaliga `reply_to_message_id` (nullable foreign key to messages)
  - `thread_id` (nullable, thread root message ID)

#### Backend (FastAPI)
**Manba**: `AdekolaThanni/Telegram-Clone`
- **Fayl**: `alfaconnect/api/routes/chat.py`
- **Qo'shiladigan endpoint**:
  - `POST /chat/{chat_id}/messages` - Request body'ga `reply_to_message_id` qo'shish
- **Fayl**: `alfaconnect/database/webapp/message_queries.py`
- **Qo'shiladigan funksiyalar**:
  - `create_message()` - `reply_to_message_id` parametrini qo'shish
  - `get_message_thread(thread_id)` - Thread xabarlarini qaytarish

#### Frontend (Next.js)
**Manba**: `samarbadriddin0v/telegram-clone`
- **Fayl**: `webapp/app/components/shared/MessageBubble.tsx`
- **Qo'shiladigan kod**:
  - Reply preview (xabar ustida reply qilingan xabar ko'rinishi)
  - Reply button (context menu yoki long-press)
- **Fayl**: `webapp/app/components/shared/InputBar.tsx`
- **Qo'shiladigan kod**:
  - Reply mode (reply qilinganda input bar'da preview)
  - Reply cancel button
- **Fayl**: `webapp/app/components/shared/ThreadView.tsx` (yangi, optional)
- **Qo'shiladigan kod**:
  - Thread view (reply qilingan xabarlar ro'yxati)

#### WebSocket Events
- **Fayl**: `alfaconnect/api/routes/websocket.py`
- **O'zgartirish yo'q** - Mavjud `message.new` event ishlatiladi

### Implementatsiya Ketma-ketligi
1. Database schema o'zgartirish
2. Backend reply message funksiyasi
3. Backend reply API endpoint
4. Frontend reply button va preview
5. Frontend InputBar reply mode
6. Frontend thread view (optional)
7. Testing va optimization

### Kutilayotgan Natija
Xabarga reply berish mumkin, reply qilingan xabar preview ko'rsatiladi, thread view'da barcha replylar ko'rsatiladi.

---

## Umumiy Implementatsiya Strategiyasi

### Prioritizatsiya
1. **Yuqori prioritet** (tez natija):
   - BOB 1: Typing Indicators
   - BOB 2: Message Reactions
   - BOB 3: Message Search

2. **O'rta prioritet** (foydali funksiyalar):
   - BOB 4: Message Forwarding
   - BOB 6: Media Gallery
   - BOB 8: Chat Pinning

3. **Past prioritet** (qo'shimcha funksiyalar):
   - BOB 5: Voice Messages
   - BOB 7: Message Editing
   - BOB 9: Read Receipts Yaxshilash
   - BOB 10: Message Threading

### Testing Strategiyasi
Har bir bob yakunlangandan keyin:
1. Unit testing (backend funksiyalar)
2. Integration testing (API endpoints)
3. Frontend component testing
4. End-to-end testing (butun funksiya)
5. Performance testing (yuk ostida)

### Documentation
Har bir bob uchun:
1. API documentation (Swagger/OpenAPI)
2. Component documentation (JSDoc)
3. Database schema documentation
4. User guide (qanday ishlatish)

### Deployment Strategiyasi
1. Har bir bob alohida branch'da
2. Code review
3. Staging environment'da test
4. Production'ga deploy
5. Monitoring va error tracking

---

## Xulosa

Bu reja 10 ta asosiy funksiyani ketma-ketlikda implementatsiya qilish uchun mo'ljallangan. Har bir bob mustaqil implementatsiya qilinadi va to'liq yakunlangandan keyin keyingi bobga o'tiladi. 

**Keyingi qadam**: BOB 1 (Typing Indicators) dan boshlash va har bir qadamni puxta bajarish.


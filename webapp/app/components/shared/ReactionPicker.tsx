"use client"

interface ReactionPickerProps {
  onSelect: (emoji: string) => void
  onClose: () => void
}

const POPULAR_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥", "👏", "🎉"]

export default function ReactionPicker({ onSelect, onClose }: ReactionPickerProps) {
  const handleEmojiClick = (emoji: string) => {
    onSelect(emoji)
    onClose()
  }

  return (
    <div className="absolute bottom-full left-0 mb-2 bg-white border border-blue-200 rounded-lg shadow-lg p-2 z-50">
      <div className="grid grid-cols-4 gap-1">
        {POPULAR_EMOJIS.map((emoji) => (
          <button
            key={emoji}
            onClick={() => handleEmojiClick(emoji)}
            className="w-8 h-8 xs:w-9 xs:h-9 sm:w-10 sm:h-10 flex items-center justify-center rounded-lg text-lg xs:text-xl sm:text-2xl transition-all hover:scale-110 hover:bg-blue-50"
          >
            {emoji}
          </button>
        ))}
      </div>
    </div>
  )
}


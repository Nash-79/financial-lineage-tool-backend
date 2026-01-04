# OpenSpec Proposal: Interactive Chat Features

## Metadata
- **Authors**: Antigravity
- **Status**: Implemented
- **Created**: 2026-01-04
- **Target Completion**: 2026-01-04

## Motivation
To modernize the chat interface and provide users with greater control over their conversation history, specifically the ability to delete irrelevant messages and edit/retry queries to refine results.

## Implemented Changes

### 1. Frontend Architecture
- **State Management (`src/stores/appStore.ts`)**:
    - Added `deleteMessage(sessionId, messageId)` action: Removes a message from the local session state.
    - Added `editMessage(sessionId, messageId, newContent)` action: Updates message content and truncates subsequent history to maintain conversation consistency.
    - Added `regenerateLastMessage(sessionId, assistantMessageId)` action: Removes the assistant message and triggers a re-fetch.
    - Unified `Message` interface to include `id`, `citations`, and `metadata`.

- **API Layer (`src/lib/api.ts`)**:
    - Aligned `ChatMessage` and `ChatResponse` interfaces with the store's `Message` type.
    - Added support for `sources` and `metadata` in responses.

### 2. User Interface (`src/components/Chat/`)
- **MessageItem Component**:
    - **Visuals**: Implemented distinct "bubble" styling for User (Primary) vs Assistant (Card) messages.
    - **Avatars**: Added "You" and "Bot" indicators.
    - **Actions**:
        - **Delete**: "Trash" icon available on hover for all messages.
        - **Edit**: "Pencil" icon available on hover for User messages.
    - **Edit Mode**: Inline textarea with "Save & Retry" and "Cancel" controls.
    - **Output features**:
        - Collapsible Code Blocks with "Copy" button.
        - Tabbed view for Graph outputs (Rendered vs JSON).
        - Markdown table support with horizontal scrolling.

- **Chat Page (`src/pages/Chat.tsx`)**:
    - Handlers implemented for `handleMessageDelete` and `handleMessageEdit`.
    - Edit logic triggers a re-fetch of the assistant response using the modified history context.

### 3. Backend Considerations
- No direct backend changes were required for the *actions* themselves, as state is managed client-side and the full context is resent on each request.
- Backend endpoints were verified to support the updated `history` structure.

## Verification
- **Build**: `npm run build` passes successfully.
- **Functionality**:
    - Deleting a message instantly removes it from the UI.
    - Editing a user message updates the text, removes subsequent messages, and triggers a new LLM generation.
    - UI elements (Copy, Code Blocks, Tables) render correctly in both light and dark modes.

## [NEW] Chat Memory System (M9)

### 1. Vectorized Long-Term Memory
- **Goal**: Enable the agent to recall past project details without re-sending the entire chat history.
- **Components**:
    - **Search Engine**: Qdrant `chat_history` collection.
    - **Service**: `MemoryService` for sync/async operations.
    - **Indexing**: User queries and Assistant responses are vectorized and stored.

### 2. Async Management
- **Storage**: Triggered asynchronously via `BackgroundTasks` after the HTTP response is sent to ensure <200ms API latency overhead.
- **Deletion**: When a user deletes a session, an async task prunes the corresponding vectors.

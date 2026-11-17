// app/chat/translations.ts
// ============================================================
// CHAT MODULE TRANSLATIONS
// All translation keys used by the chat page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const CHAT = {
    connections_load_error: { key: "chat.connections_load_error", fallback: "Failed to load connections" },
    models_load_error: { key: "chat.models_load_error", fallback: "Failed to load models" },
    load_error: { key: "chat.load_error", fallback: "Failed to load chats" },
    select_connection_first: { key: "chat.select_connection_first", fallback: "Please select an AI connection first." },
    connection_not_found: { key: "chat.connection_not_found", fallback: "AI connection not found or not accessible" },
    send_error: { key: "chat.send_error", fallback: "Failed to send message" },
    rename_empty: { key: "chat.rename_empty", fallback: "Title cannot be empty" },
    rename_error: { key: "chat.rename_error", fallback: "Failed to rename chat" },
    rename_success: { key: "chat.rename_success", fallback: "Chat renamed" },
    delete_confirm: { key: "chat.delete_confirm", fallback: "Are you sure you want to delete this chat?" },
    delete_error: { key: "chat.delete_error", fallback: "Failed to delete chat" },
    delete_success: { key: "chat.delete_success", fallback: "Chat deleted" },
    title: { key: "chat.title", fallback: "Chat" },
    no_connections_message: { key: "chat.no_connections_message", fallback: "You need to define at least one AI connection before you can use Chat." },
    go_to_ai_settings: { key: "chat.go_to_ai_settings", fallback: "Go to AI Settings" },
    history: { key: "chat.history", fallback: "Chat History" },
    no_chats: { key: "chat.no_chats", fallback: "No chats yet" },
    rename: { key: "chat.rename", fallback: "Rename" },
    delete: { key: "chat.delete", fallback: "Delete" },
    new_chat: { key: "chat.new_chat", fallback: "New Chat" },
    select_connection: { key: "chat.select_connection", fallback: "AI Connection" },
    select_connection_placeholder: { key: "chat.select_connection_placeholder", fallback: "Select an AI connection" },
    select_model: { key: "chat.select_model", fallback: "Model" },
    select_model_placeholder: { key: "chat.select_model_placeholder", fallback: "Select a model" },
    no_models: { key: "chat.no_models", fallback: "No models available for this connection" },
    no_chat_selected: { key: "chat.no_chat_selected", fallback: "No active chat" },
    empty_state: { key: "chat.empty_state", fallback: "Send a message to start a conversation." },
    input_placeholder: { key: "chat.input_placeholder", fallback: "Type your message..." },
} as const;
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Send, PlusCircle, MessageSquare, XCircle, Pencil, Trash2, Loader2, Lock, UserPlus } from "lucide-react";
import Link from "next/link";
import AudioToggle from "@/components/audio-toggle";
import AudioSettingsDialog from "@/components/audio-settings-dialog";
import CopyButton from "@/components/copy-button";
import { useSpeechOutput } from "@/hooks/use-speech";
import { useSpeechInput } from "@/hooks/use-speech-input";
import { getCachedSettings, setCachedSettings } from "@/lib/audio-settings";
import { useAI } from "@/lib/ai-context";

// Import translations for this module
import { CHAT } from "./translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
import { AI } from "@/app/ai/translations";
import { formatDateTime, formatTime } from "@/lib/date-format";

interface Message {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

interface Chat {
  id: number;
  title: string;
  messages: Message[];
  updatedAt: string;
}

interface Model {
  id: number;
  modelCode: string;
  modelName: string;
  comment: string | null;
}

interface AvailableConnection {
  id: string;
  connectionId: number;
  name: string;
  provider: string;
  aiConnectionGroup: string;
  userId: string;
  userName: string;
  isOwn: boolean;
}

function ChatContent() {
  const router = useRouter();
  const { isLanguageLoaded, language } = useTranslation();
  const translate = useTranslate();
  const { defaultConnectionId } = useAI();
  const [connections, setConnections] = useState<AvailableConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [selectedModelCode, setSelectedModelCode] = useState<string | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentChatId, setCurrentChatId] = useState<number | null>(null);
  const [currentChat, setCurrentChat] = useState<Chat | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [speakerEnabled, setSpeakerEnabled] = useState(false);
    const [micEnabled, setMicEnabled] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [speakerMuted, setSpeakerMuted] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  // Rename state
  const [editingChatId, setEditingChatId] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const renameInputRef = useRef<HTMLInputElement>(null);

    const isExampleUser = userRole?.isExampleUser === true;

    // Audio output: speak the last non-user message (AI response)
    const lastAssistantContent = currentChat?.messages?.slice().reverse().find((m: any) => m.role !== "user")?.content ?? "";
    const { speechOutputError, speechState, pause, resume, stop, volume, setVolume } =
        useSpeechOutput(lastAssistantContent, speakerEnabled, "general");

    // Audio input: speech-to-text
    const { transcript, speechInputError } = useSpeechInput(micEnabled);

    // Pipe transcript into input message field
    useEffect(() => { if (transcript) setInputMessage(transcript); }, [transcript]);

    // Handle audio errors
    useEffect(() => { if (speechOutputError) setErrorMessage(speechOutputError); }, [speechOutputError]);
    useEffect(() => { if (speechInputError) setErrorMessage(speechInputError); }, [speechInputError]);

    useEffect(() => {
        const fetchUserRole = async () => {
      try {
        const res = await apiFetch("/api/user/role");
        if (res.ok) {
          const data = await res.json();
          setUserRole(data);
        }
      } catch (error) {
        console.error("Failed to fetch user role:", error);
      } finally {
        setLoadingRole(false);
      }
    };
    fetchUserRole();
  }, []);

  const getConnectionLabel = (conn: AvailableConnection) => {
    const name = conn.name || conn.provider || String(conn.connectionId);
    if (conn.isOwn) {
      return `${name} (${conn.provider})`;
    } else {
      return `* ${name} (${conn.provider})`;
    }
  };

  const fetchAvailableConnections = async () => {
    setLoadingConnections(true);
    try {
      const res = await apiFetch("/api/user/ai-connections/available");
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.connections_load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setConnections(data.connections || []);
      if (data.connections && data.connections.length > 0) {
        const firstId = data.connections[0].id;
        setSelectedConnectionId(firstId);
      } else {
        setSelectedConnectionId(null);
      }
    } catch (error: any) {
      console.error("Error fetching connections:", error);
      setConnections([]);
      setSelectedConnectionId(null);
    } finally {
      setLoadingConnections(false);
    }
  };

  const fetchModels = async (connectionId: string) => {
    setLoadingModels(true);
    try {
      const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models?enabled=true`);
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.models_load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setModels(data.models || []);
      if (data.models && data.models.length > 0) {
        setSelectedModelCode(data.models[0].modelCode);
      } else {
        setSelectedModelCode(null);
      }
    } catch (error: any) {
      console.error("Error fetching models:", error);
      setModels([]);
      setSelectedModelCode(null);
    } finally {
      setLoadingModels(false);
    }
  };

  const fetchChats = async (): Promise<Chat[]> => {
    try {
      const res = await apiFetch("/api/chat/");
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      return data.chats || [];
    } catch (error: any) {
      console.error("Error fetching chats:", error);
      return [];
    }
  };

  const fetchChat = async (chatId: number): Promise<Chat> => {
    const res = await apiFetch(`/api/chat/${chatId}`);
    if (!res.ok) {
      let errorData: any = {};
      try {
        const text = await res.text();
        if (text) {
          errorData = JSON.parse(text);
        }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.load_error);
        throw new Error(errorMsg);
    }
    return await res.json();
  };

  const sendMessage = async (message: string, chatId?: number): Promise<Chat> => {
    if (!selectedConnectionId) {
      throw new Error(translate(CHAT.select_connection_first));
    }
    
    const selectedConn = connections.find(c => c.id === selectedConnectionId);
    if (!selectedConn) {
      throw new Error(translate(CHAT.connection_not_found));
    }
    
    const payload: any = {
      connectionId: selectedConn.connectionId,
      message: message,
    };
    if (selectedModelCode) {
      payload.model = selectedModelCode;
    }
    if (chatId) payload.chatId = chatId;

    const res = await apiFetch("/api/chat/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errorData: any = {};
      try {
        const text = await res.text();
        if (text) {
          errorData = JSON.parse(text);
        }
      } catch {
        // Use empty object
      }
      const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.send_error);
      throw new Error(errorMsg);
    }

    const data = await res.json();
    return data.chat;
  };

  const generateChatTitle = async (chatId: number, userMessage: string) => {
    if (!selectedConnectionId) return;
    try {
      const selectedConn = connections.find(c => c.id === selectedConnectionId);
      if (!selectedConn) return;
      
      const res = await apiFetch(`/api/chat/${chatId}/generate-title`, {
        method: "POST",
        body: JSON.stringify({
          connectionId: selectedConn.connectionId,
          userMessage: userMessage,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setChats(prev => prev.map(c => c.id === chatId ? { ...c, title: data.title } : c));
        if (currentChat && currentChat.id === chatId) {
          setCurrentChat({ ...currentChat, title: data.title });
        }
      } else {
        console.warn("Title generation failed, keeping default title.");
      }
    } catch (error) {
      console.warn("Title generation error:", error);
    }
  };

  // Load connections on mount
  useEffect(() => {
    fetchAvailableConnections();
  }, []);

  // Auto-select the default AI connection when it becomes known
  useEffect(() => {
    if (defaultConnectionId && connections.length > 0) {
      const defaultConn = connections.find(c => c.id === defaultConnectionId);
      if (defaultConn) {
        setSelectedConnectionId(defaultConnectionId);
      }
    }
  }, [defaultConnectionId, connections]);

  // Load models when connection changes
  useEffect(() => {
    if (selectedConnectionId !== null) {
      const conn = connections.find(c => c.id === selectedConnectionId);
      if (conn) {
        fetchModels(selectedConnectionId);
      }
    }
  }, [selectedConnectionId, connections]);

  // Load chats on mount AND when connection changes (to reset chat state)
  useEffect(() => {
    if (selectedConnectionId !== null) {
      loadChats();
    }
  }, [selectedConnectionId]);

  // Separate effect to load chats when returning to the page
  useEffect(() => {
    if (selectedConnectionId !== null && connections.length > 0) {
      loadChats();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadChats = async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const chatsList = await fetchChats();
      setChats(chatsList);
      if (chatsList.length > 0 && currentChatId === null) {
        const latestChat = chatsList[0];
        setCurrentChatId(latestChat.id);
        const fullChat = await fetchChat(latestChat.id);
        setCurrentChat(fullChat);
      } else if (chatsList.length > 0 && currentChatId !== null) {
        const existingChat = chatsList.find((c: Chat) => c.id === currentChatId);
        if (existingChat) {
          const fullChat = await fetchChat(currentChatId);
          setCurrentChat(fullChat);
        } else {
          const latestChat = chatsList[0];
          setCurrentChatId(latestChat.id);
          const fullChat = await fetchChat(latestChat.id);
          setCurrentChat(fullChat);
        }
      }
    } catch (error: any) {
      const msg = error.message || translate(CHAT.load_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const selectChat = async (chatId: number) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const chat = await fetchChat(chatId);
      setCurrentChat(chat);
      setCurrentChatId(chatId);
    } catch (error: any) {
      const msg = error.message || translate(CHAT.load_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!inputMessage.trim()) return;
    if (!selectedConnectionId) {
      const msg = translate(CHAT.select_connection_first);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    if (isExampleUser) {
      const msg = translate(COMPONENTS.readonly_wrapper);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    const oldChatId = currentChatId;

    setIsSending(true);
    setErrorMessage(null);
    try {
      const updatedChat = await sendMessage(inputMessage, currentChatId || undefined);
      setCurrentChat(updatedChat);
      setCurrentChatId(updatedChat.id);
      setChats(prevChats => {
        const existing = prevChats.find(c => c.id === updatedChat.id);
        if (existing) {
          return prevChats.map(c => c.id === updatedChat.id ? updatedChat : c);
        } else {
          return [updatedChat, ...prevChats];
        }
      });
      setInputMessage("");

      if (oldChatId === null) {
        await generateChatTitle(updatedChat.id, inputMessage);
      }
    } catch (error: any) {
      const msg = error.message || translate(CHAT.send_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsSending(false);
    }
  };

  const startNewChat = () => {
    if (isExampleUser) {
      const msg = translate(COMPONENTS.readonly_wrapper);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    setCurrentChat(null);
    setCurrentChatId(null);
    setInputMessage("");
    setErrorMessage(null);
  };

  const dismissError = () => setErrorMessage(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [currentChat?.messages]);

  useEffect(() => {
    if (editingChatId !== null && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [editingChatId]);

  const handleRenameStart = (chat: Chat) => {
    if (isExampleUser) {
      const msg = translate(COMPONENTS.readonly_wrapper);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    setEditingChatId(chat.id);
    setEditingTitle(chat.title);
  };

  const handleRenameCancel = () => {
    setEditingChatId(null);
    setEditingTitle("");
  };

  const handleRenameSave = async (chatId: number) => {
    if (!editingTitle.trim()) {
      toast.error(translate(CHAT.rename_empty));
      return;
    }
    try {
      const res = await apiFetch(`/api/chat/${chatId}`, {
        method: "PATCH",
        body: JSON.stringify({ title: editingTitle.trim() }),
      });
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.rename_error);
        throw new Error(errorMsg);
      }
      const updatedChat = await res.json();
      setChats(prev => prev.map(c => c.id === chatId ? { ...c, title: updatedChat.title } : c));
      if (currentChat && currentChat.id === chatId) {
        setCurrentChat({ ...currentChat, title: updatedChat.title });
      }
      toast.success(translate(CHAT.rename_success));
    } catch (error: any) {
      toast.error(error.message || translate(CHAT.rename_error));
    } finally {
      setEditingChatId(null);
    }
  };

  const handleDeleteChat = async (chatId: number) => {
    if (isExampleUser) {
      const msg = translate(COMPONENTS.readonly_wrapper);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    try {
      const res = await apiFetch(`/api/chat/${chatId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.delete_error);
        throw new Error(errorMsg);
      }
      setChats(prev => prev.filter(c => c.id !== chatId));
      if (currentChat && currentChat.id === chatId) {
        setCurrentChat(null);
        setCurrentChatId(null);
      }
      toast.success(translate(CHAT.delete_success));
    } catch (error: any) {
      toast.error(error.message || translate(CHAT.delete_error));
    }
  };

  const selectedModel = models.find(m => m.modelCode === selectedModelCode);
  const modelComment = selectedModel?.comment;

  if (!isLanguageLoaded || loadingConnections || loadingRole) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // If Example User, show read-only view
  if (isExampleUser) {
    return (
      <div className="max-w-6xl mx-auto py-6 space-y-4 flex flex-col md:flex-row gap-6 h-auto md:h-[calc(100vh-100px)]">
        <div className="w-full md:w-64 md:flex-shrink-0 h-auto md:h-full overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">{translate(CHAT.history)}</h2>
            <Button variant="ghost" size="sm" disabled>
              <PlusCircle className="h-4 w-4" />
            </Button>
          </div>
          <div className="h-[calc(100%-40px)] overflow-y-auto border rounded-md p-2 opacity-60">
            {isLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            ) : chats.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">{translate(CHAT.no_chats)}</p>
            ) : (
              chats.map((chat) => (
                <div
                  key={chat.id}
                  className={`p-2 rounded-md hover:bg-muted transition-colors ${
                    chat.id === currentChatId ? "bg-muted" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={() => selectChat(chat.id)}
                    >
                      <span className="text-sm truncate block">
                        {chat.title || `Chat ${chat.id}`}
                      </span>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatDateTime(chat.updatedAt)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col min-w-0 h-full">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4 flex-shrink-0">
            <h1 className="text-3xl font-bold">{translate(CHAT.title)}</h1>
            <div className="flex items-center gap-2">
              <Button variant="outline" disabled>
                {translate(CHAT.new_chat)}
              </Button>
            </div>
          </div>

          <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center mb-4">
            <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
            <p className="text-sm mb-4">
              {translate(COMPONENTS.readonly_wrapper)}
            </p>
            <Link href="/register">
              <Button>
                <UserPlus className="h-4 w-4 me-2" />
                {translate(COMPONENTS.example_user_banner.register_button)}
              </Button>
            </Link>
          </div>

          <div className="flex flex-wrap items-center gap-4 mb-4 flex-shrink-0 opacity-60">
            <div className="w-full md:w-64">
              <Label>{translate(CHAT.select_connection)}</Label>
              <Select value={selectedConnectionId || ""} disabled>
                <SelectTrigger>
                  <SelectValue placeholder={translate(CHAT.select_connection_placeholder)} />
                </SelectTrigger>
              </Select>
            </div>
            <div className="w-full md:w-64">
              <Label>{translate(CHAT.select_model)}</Label>
              <Select value={selectedModelCode || ""} disabled>
                <SelectTrigger>
                  <SelectValue placeholder={translate(CHAT.select_model_placeholder)} />
                </SelectTrigger>
              </Select>
            </div>
          </div>

          <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <CardHeader className="pb-2 flex-shrink-0">
              <CardTitle className="text-lg">
                {currentChat ? currentChat.title : translate(CHAT.no_chat_selected)}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col overflow-hidden p-4 pt-0">
              <div className="flex-1 overflow-y-auto space-y-2 mb-4 p-2 bg-muted/30 rounded-md opacity-60">
                {currentChat?.messages.length ? (
                  currentChat.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-2 ${
                          msg.role === "user"
                            ? "bg-primary text-primary-foreground"
                            : "bg-secondary text-secondary-foreground"
                        }`}
                      >
                        <div className="flex items-start gap-1">
                          <p className="whitespace-pre-wrap text-sm flex-1">{msg.content}</p>
                          <CopyButton text={msg.content} />
                        </div>
                        <span className="text-xs opacity-60 block mt-1">
                          {formatTime(msg.createdAt)}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    {translate(CHAT.empty_state)}
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {errorMessage && (
                <div className="px-3 py-2 bg-red-50 border-t border-red-200 text-red-800 flex items-center justify-between flex-shrink-0">
                  <span className="text-sm">{errorMessage}</span>
                  <button
                    onClick={dismissError}
                    className="text-red-500 hover:text-red-700"
                    aria-label={translate(COMMON.dismiss)}
                  >
                    <XCircle className="h-5 w-5" />
                  </button>
                </div>
              )}

              <div className="flex gap-2 flex-shrink-0 opacity-60">
                <Input dir="auto"
                  placeholder={translate(CHAT.input_placeholder)}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  disabled
                  className="flex-1"
                />
                <Button disabled>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
        <AudioSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} chatType="general" />
      </div>
    );
  }

  // Normal user view - full access

  return (
    <div className="chat-layout">
      {/* The recipe page's arrangement, followed here so the chat owns the screen: a fixed-height
          grid with page scroll removed, the history in one column, and the chat in the other with
          the title and controls as its own header rather than in rows above a card. */}
      <style>{`
        .chat-layout {
          display: grid;
          grid-template-columns: 260px 1fr;
          height: calc(100vh - 64px);
          overflow: hidden;
        }
        .chat-layout > .chat-sessions-panel {
          overflow: auto;
          background: var(--card);
          border-right: 1px solid var(--border);
          padding: 0.75rem;
        }
        .chat-layout > .chat-main-panel {
          display: flex;
          flex-direction: column;
          min-width: 0;
          overflow: hidden;
        }
        @media (max-width: 1023px) {
          .chat-layout { grid-template-columns: 1fr; }
          .chat-layout > .chat-sessions-panel { display: none; }
        }
      `}</style>

      <div className="chat-sessions-panel">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{translate(CHAT.history)}</h2>
          <Button variant="ghost" size="sm" onClick={startNewChat}>
            <PlusCircle className="h-4 w-4" />
          </Button>
        </div>
        <div className="overflow-y-auto border rounded-md p-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : chats.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">{translate(CHAT.no_chats)}</p>
          ) : (
            chats.map((chat) => (
              <div
                key={chat.id}
                className={`p-2 rounded-md hover:bg-muted transition-colors ${
                  chat.id === currentChatId ? "bg-muted" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => selectChat(chat.id)}
                  >
                    {editingChatId === chat.id ? (
                      <div className="flex items-center gap-1">
                        <Input dir="auto"
                          ref={renameInputRef}
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              handleRenameSave(chat.id);
                            } else if (e.key === "Escape") {
                              handleRenameCancel();
                            }
                          }}
                          onBlur={() => handleRenameSave(chat.id)}
                          className="h-6 text-sm"
                        />
                      </div>
                    ) : (
                      <span className="text-sm truncate block">
                        {chat.title || `Chat ${chat.id}`}
                      </span>
                    )}
                  </div>
                  {editingChatId !== chat.id && (
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => handleRenameStart(chat)}
                        className="text-muted-foreground hover:text-foreground p-0.5"
                        title={translate(CHAT.rename)}
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                      <button
                        onClick={() => handleDeleteChat(chat.id)}
                        className="text-muted-foreground hover:text-destructive p-0.5"
                        title={translate(CHAT.delete)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDateTime(chat.updatedAt)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="chat-main-panel">
        {/* Header: the title and the controls, so nothing sits above the messages */}
        <div className="border-b border-border bg-card px-3 py-2 flex flex-wrap items-center gap-2">
          <span className="font-semibold text-sm">{translate(CHAT.title)}</span>
          <span className="text-xs text-muted-foreground truncate max-w-[160px] me-1">
            {currentChat ? currentChat.title : translate(CHAT.no_chat_selected)}
          </span>
          <span className="text-xs text-muted-foreground">{translate(CHAT.select_connection)}</span>
          <div className="relative flex items-center">
            <span className="text-red-500 font-bold me-1" aria-hidden="true">*</span>
            <Select
              value={selectedConnectionId || ""}
              onValueChange={(val) => {
                if (val !== null) setSelectedConnectionId(val);
              }}
            >
              <SelectTrigger id="connection-select" className="h-8 w-[190px] text-xs">
                <SelectValue placeholder={translate(CHAT.select_connection_placeholder)}>
                  {selectedConnectionId !== null ? getConnectionLabel(connections.find(c => c.id === selectedConnectionId)!) : ""}
                </SelectValue>
              </SelectTrigger>
              <SelectContent className="max-w-[280px]">
                {connections.map((conn) => {
                  const label = getConnectionLabel(conn);
                  return (
                    <SelectItem key={conn.id} value={conn.id}>
                      <span className="truncate">{label}</span>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          {connections.length === 0 && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-2 py-1">
              {translate(AI.no_ai_connections)}
            </p>
          )}

          <span className="text-xs text-muted-foreground">{translate(CHAT.select_model)}</span>
          <div className="relative flex items-center">
            <span className="text-red-500 font-bold me-1" aria-hidden="true">*</span>
            <Select
              value={selectedModelCode || ""}
              onValueChange={(val) => {
                if (val !== null) setSelectedModelCode(val);
              }}
              disabled={loadingModels || models.length === 0}
            >
              <SelectTrigger id="model-select" className="h-8 w-[200px] text-xs">
                <SelectValue placeholder={translate(CHAT.select_model_placeholder)}>
                  {selectedModelCode ? models.find(m => m.modelCode === selectedModelCode)?.modelName || selectedModelCode : ""}
                </SelectValue>
              </SelectTrigger>
              <SelectContent className="min-w-[200px] max-w-[320px]">
                {models.map((model) => (
                  <SelectItem key={model.id} value={model.modelCode}>
                    <span className="truncate">{model.modelName} ({model.modelCode})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {loadingModels && <span className="text-xs text-muted-foreground">{translate(COMMON.loading)}</span>}
          {!loadingModels && models.length === 0 && (
            <span className="text-xs text-muted-foreground">{translate(CHAT.no_models)}</span>
          )}
          {modelComment && (
            <span className="text-xs text-muted-foreground italic">{modelComment}</span>
          )}
          <Button variant="outline" size="sm" className="ms-auto" onClick={startNewChat}>
            {translate(CHAT.new_chat)}
          </Button>
        </div>

          {/* Messages - the chat owns whatever height is left */}
            <div className="flex-1 min-h-0 overflow-y-auto space-y-2 m-3 p-2 bg-muted/30 rounded-md">
              {currentChat?.messages.length ? (
                currentChat.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2 ${
                        msg.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary text-secondary-foreground"
                      }`}
                    >
                      <div className="flex items-start gap-1">
                        <p className="whitespace-pre-wrap text-sm flex-1">{msg.content}</p>
                        <CopyButton text={msg.content} />
                      </div>
                      <span className="text-xs opacity-60 block mt-1">
                        {formatTime(msg.createdAt)}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  {translate(CHAT.empty_state)}
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {errorMessage && (
              <div className="px-3 py-2 bg-red-50 border-t border-red-200 text-red-800 flex items-center justify-between flex-shrink-0">
                <span className="text-sm">{errorMessage}</span>
                <button
                  onClick={dismissError}
                  className="text-red-500 hover:text-red-700"
                  aria-label={translate(COMMON.dismiss)}
                >
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            )}

            <div className="flex gap-2 flex-shrink-0 items-center p-3 border-t">
              <AudioToggle
                micEnabled={micEnabled} onMicChange={setMicEnabled}
                speakerEnabled={speakerEnabled} onSpeakerChange={setSpeakerEnabled}
                volume={volume} onVolumeChange={setVolume}
                speakerMuted={speakerMuted}
                onSpeakerMuteToggle={() => { const next = !speakerMuted; setSpeakerMuted(next); setSpeakerEnabled(!next); const s = getCachedSettings("general"); s.speakerMuted = next; setCachedSettings("general", s); }}
                speechState={speechState} onPause={pause} onResume={resume} onStop={stop}
                onSettingsClick={() => setSettingsOpen(true)}
              />
              <Input dir="auto"
                placeholder={translate(CHAT.input_placeholder)}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={isSending}
                className="flex-1"
              />
              <Button onClick={handleSend} disabled={isSending}>
                {isSending ? (
                  <span className="animate-spin">⏳</span>
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
      </div>
      <AudioSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} chatType="general" />
    </div>
  );
}

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <ChatContent />
    </ProtectedRoute>
  );
}
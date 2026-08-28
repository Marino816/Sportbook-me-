import { useState, useRef, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from "react-native";
import { sendAIChat, setStrategyMode, AIMessage, AIChatContext } from "../../lib/ai-api";

const QUICK_ACTIONS = [
  { label: "🏗️ Build GPP lineup", prompt: "Build my best GPP lineup tonight for DraftKings NBA." },
  { label: "📊 Top values", prompt: "Who are the highest projected value plays tonight?" },
  { label: "🔄 Pivots", prompt: "Show me lower-owned tournament pivots for the main slate." },
  { label: "⚖️ Compare", prompt: "Compare the top two point guards tonight." },
  { label: "🩺 Injuries", prompt: "What's the latest injury impact for tonight's slate?" },
  { label: "📋 Slate summary", prompt: "Give me a summary of tonight's main slate." },
];

const STRATEGY_MODES = ["Cash", "Tournament", "Single Entry", "Nuclear", "Bankroll"];

export default function AIChatScreen() {
  const [messages, setMessages] = useState<AIMessage[]>([{ role: "assistant", content: "Welcome to SB ME Intelligent AI. How can I help with your DFS research today? Ask me about lineups, projections, injuries, or strategy." }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("Tournament");
  const [convId, setConvId] = useState<string | undefined>();
  const [context, setContext] = useState<AIChatContext>({});
  const scrollRef = useRef<ScrollView>(null);

  async function handleSend(text?: string) {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput("");
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const response = await sendAIChat(msg, convId, history, context);
      if (response.conversation_id) setConvId(response.conversation_id);
      if (response.context) setContext(response.context);
      setMessages(prev => [...prev, response]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "AI service is temporarily unavailable. Please try again." }]);
    } finally { setLoading(false); }
  }

  async function handleModeSwitch(m: string) {
    setMode(m);
    try { await setStrategyMode(m.toLowerCase()); } catch {}
  }

  useEffect(() => { setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100); }, [messages]);

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.container} keyboardVerticalOffset={90}>
      {/* Strategy Mode Bar */}
      <ScrollView horizontal style={s.modeBar} contentContainerStyle={s.modeContent} showsHorizontalScrollIndicator={false}>
        {STRATEGY_MODES.map(m => (
          <TouchableOpacity key={m} style={[s.modeChip, mode === m && s.modeActive]} onPress={() => handleModeSwitch(m)}>
            <Text style={[s.modeText, mode === m && s.modeTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Messages */}
      <ScrollView ref={scrollRef} style={s.messages} contentContainerStyle={s.messagesContent}>
        {messages.map((m, i) => (
          <View key={i} style={[s.bubble, m.role === "user" ? s.userBubble : s.aiBubble]}>
            <Text style={[s.bubbleText, m.role === "user" ? s.userText : s.aiText]}>{m.content}</Text>
            {m.modules && m.modules.length > 0 && (
              <Text style={s.modules}>{m.modules.join(" · ")}</Text>
            )}
            {m.confidence != null && (
              <Text style={s.meta}>Confidence: {Math.round(m.confidence * 100)}% · Freshness: {m.freshness || "unknown"}</Text>
            )}
          </View>
        ))}
        {loading && <ActivityIndicator style={{ marginVertical: 12 }} color="#c9a84c" />}
      </ScrollView>

      {/* Quick Actions */}
      <ScrollView horizontal style={s.quickBar} contentContainerStyle={s.quickContent} showsHorizontalScrollIndicator={false}>
        {QUICK_ACTIONS.map((a, i) => (
          <TouchableOpacity key={i} style={s.quickChip} onPress={() => handleSend(a.prompt)}>
            <Text style={s.quickText}>{a.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Input */}
      <View style={s.inputRow}>
        <TextInput style={s.input} placeholder="Ask SB ME Intelligent AI..." placeholderTextColor="#666" value={input} onChangeText={setInput} onSubmitEditing={() => handleSend()} returnKeyType="send" />
        <TouchableOpacity style={s.sendBtn} onPress={() => handleSend()} disabled={loading}>
          <Text style={s.sendText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a" },
  modeBar: { maxHeight: 44, borderBottomWidth: 1, borderColor: "#222" },
  modeContent: { paddingHorizontal: 12, gap: 8, alignItems: "center" },
  modeChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#333" },
  modeActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  modeText: { color: "#888", fontSize: 12, fontWeight: "600" },
  modeTextActive: { color: "#c9a84c" },
  messages: { flex: 1 },
  messagesContent: { padding: 16, gap: 12 },
  bubble: { maxWidth: "85%", borderRadius: 16, padding: 14 },
  userBubble: { alignSelf: "flex-end", backgroundColor: "#c9a84c" },
  aiBubble: { alignSelf: "flex-start", backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#333" },
  bubbleText: { fontSize: 15, lineHeight: 21 },
  userText: { color: "#000" },
  aiText: { color: "#fff" },
  modules: { fontSize: 10, color: "#888", marginTop: 6, textTransform: "uppercase" },
  meta: { fontSize: 10, color: "#666", marginTop: 4 },
  quickBar: { maxHeight: 48, borderTopWidth: 1, borderColor: "#222" },
  quickContent: { paddingHorizontal: 12, gap: 8, alignItems: "center" },
  quickChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#333" },
  quickText: { color: "#888", fontSize: 11 },
  inputRow: { flexDirection: "row", padding: 12, gap: 8, borderTopWidth: 1, borderColor: "#222" },
  input: { flex: 1, backgroundColor: "#0a0f24", color: "#fff", borderRadius: 24, paddingHorizontal: 16, paddingVertical: 12, fontSize: 15, borderWidth: 1, borderColor: "#333" },
  sendBtn: { backgroundColor: "#c9a84c", borderRadius: 24, paddingHorizontal: 20, justifyContent: "center" },
  sendText: { color: "#000", fontWeight: "700", fontSize: 14 },
});
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'dart:math' as math;
import '../../core/app_colors.dart';
import '../../providers/ai_agent_provider.dart';
import '../../providers/auth_provider.dart';

class AIVoiceScreen extends StatefulWidget {
  const AIVoiceScreen({super.key});

  @override
  State<AIVoiceScreen> createState() => _AIVoiceScreenState();
}

class _AIVoiceScreenState extends State<AIVoiceScreen>
    with TickerProviderStateMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  late AnimationController _pulseController;
  late AnimationController _waveController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);

    _waveController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    )..repeat();

    _initializeConversation();
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _pulseController.dispose();
    _waveController.dispose();
    super.dispose();
  }

  Future<void> _initializeConversation() async {
    final user = context.read<AuthProvider>().user;
    final patientId = user?['id'] ?? 1;
    await context.read<AIAgentProvider>().startConversation(patientId);
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: AppColors.success,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              'AI Health Assistant',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.more_vert, color: AppColors.textSecondary),
            onPressed: () => _showOptionsMenu(context),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(child: _buildMessagesList()),
          _buildInputArea(),
        ],
      ),
    );
  }

  Widget _buildMessagesList() {
    return Consumer<AIAgentProvider>(
      builder: (context, provider, _) {
        if (provider.messages.isEmpty) {
          return _buildEmptyState();
        }

        WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.all(20),
          itemCount: provider.messages.length + (provider.isLoading ? 1 : 0),
          itemBuilder: (context, index) {
            if (index == provider.messages.length) {
              return _buildTypingIndicator();
            }
            final message = provider.messages[index];
            return _buildMessageBubble(message);
          },
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.psychology_rounded,
              color: Colors.white,
              size: 50,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Hello! I\'m your AI Assistant',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              'Ask me about your medications, vitals, or health concerns',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
                height: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 32),
          _buildSuggestionChips(),
        ],
      ),
    );
  }

  Widget _buildSuggestionChips() {
    final suggestions = [
      'Show my vitals',
      'Medication reminders',
      'Health tips',
    ];

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: suggestions.map((text) {
        return ActionChip(
          label: Text(text),
          onPressed: () => _sendMessage(text),
          backgroundColor: AppColors.primaryLighter,
          labelStyle: TextStyle(
            color: AppColors.primary,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: BorderSide.none,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        );
      }).toList(),
    );
  }

  Widget _buildMessageBubble(ChatMessage message) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment: message.isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!message.isUser) ...[
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                gradient: AppColors.primaryGradient,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.psychology,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment: message.isUser
                  ? CrossAxisAlignment.end
                  : CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                  decoration: BoxDecoration(
                    color: message.isUser
                        ? AppColors.primary
                        : AppColors.surface,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(20),
                      topRight: const Radius.circular(20),
                      bottomLeft: Radius.circular(message.isUser ? 20 : 4),
                      bottomRight: Radius.circular(message.isUser ? 4 : 20),
                    ),
                    border: message.isUser
                        ? null
                        : Border.all(color: AppColors.border),
                  ),
                  child: Text(
                    message.text,
                    style: TextStyle(
                      fontSize: 15,
                      color: message.isUser
                          ? Colors.white
                          : AppColors.textPrimary,
                      height: 1.4,
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  DateFormat('hh:mm a').format(message.timestamp),
                  style: TextStyle(fontSize: 11, color: AppColors.textTertiary),
                ),
              ],
            ),
          ),
          if (message.isUser) ...[
            const SizedBox(width: 12),
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppColors.primaryLighter,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.person, color: AppColors.primary, size: 20),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.psychology, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTypingDot(0),
                const SizedBox(width: 4),
                _buildTypingDot(1),
                const SizedBox(width: 4),
                _buildTypingDot(2),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTypingDot(int index) {
    return AnimatedBuilder(
      animation: _waveController,
      builder: (context, child) {
        final offset = (index * 0.3) % 1.0;
        final animation = (_waveController.value + offset) % 1.0;
        final opacity = 0.3 + (0.7 * math.sin(animation * math.pi * 2));

        return Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: AppColors.primary.withOpacity(opacity),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }

  Widget _buildInputArea() {
    return Consumer<AIAgentProvider>(
      builder: (context, provider, _) {
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, -2),
              ),
            ],
          ),
          child: SafeArea(
            child: Row(
              children: [
                // Voice button
                GestureDetector(
                  onTapDown: (_) => _startListening(),
                  onTapUp: (_) => _stopListening(),
                  onTapCancel: () => _stopListening(),
                  child: AnimatedBuilder(
                    animation: _pulseController,
                    builder: (context, child) {
                      return Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          gradient: AppColors.primaryGradient,
                          shape: BoxShape.circle,
                          boxShadow: provider.isListening
                              ? [
                                  BoxShadow(
                                    color: AppColors.primary.withOpacity(
                                      0.4 + (_pulseController.value * 0.3),
                                    ),
                                    blurRadius:
                                        20 + (_pulseController.value * 10),
                                    spreadRadius: _pulseController.value * 5,
                                  ),
                                ]
                              : [],
                        ),
                        child: Icon(
                          provider.isListening ? Icons.mic : Icons.mic_none,
                          color: Colors.white,
                          size: 28,
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(width: 12),
                // Text input
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppColors.background,
                      borderRadius: BorderRadius.circular(28),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: TextField(
                      controller: _textController,
                      decoration: InputDecoration(
                        hintText: 'Type your message...',
                        hintStyle: TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 14,
                        ),
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 20,
                          vertical: 14,
                        ),
                      ),
                      maxLines: null,
                      textCapitalization: TextCapitalization.sentences,
                      onSubmitted: (text) {
                        if (text.trim().isNotEmpty) {
                          _sendMessage(text);
                        }
                      },
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                // Send button
                GestureDetector(
                  onTap: () {
                    final text = _textController.text.trim();
                    if (text.isNotEmpty) {
                      _sendMessage(text);
                    }
                  },
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: AppColors.primary,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.send_rounded,
                      color: Colors.white,
                      size: 20,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _sendMessage(String text) {
    context.read<AIAgentProvider>().sendMessage(text);
    _textController.clear();
  }

  void _startListening() {
    context.read<AIAgentProvider>().setListening(true);
    // TODO: Implement actual voice recognition
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Voice input coming soon!'),
        backgroundColor: AppColors.primary,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        duration: const Duration(seconds: 1),
      ),
    );
  }

  void _stopListening() {
    context.read<AIAgentProvider>().setListening(false);
  }

  void _showOptionsMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: Icon(Icons.history, color: AppColors.primary),
              title: const Text('Conversation History'),
              onTap: () {
                Navigator.pop(context);
                // TODO: Show history
              },
            ),
            ListTile(
              leading: Icon(Icons.delete_outline, color: AppColors.error),
              title: const Text('Clear Conversation'),
              onTap: () {
                Navigator.pop(context);
                context.read<AIAgentProvider>().endConversation();
              },
            ),
          ],
        ),
      ),
    );
  }
}

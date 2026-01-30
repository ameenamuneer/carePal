import 'package:flutter/material.dart';
import '../../core/app_colors.dart';
import '../../services/abdm/abdm_service.dart';
import 'package:intl/intl.dart';

class RequestsListScreen extends StatefulWidget {
  const RequestsListScreen({super.key});

  @override
  State<RequestsListScreen> createState() => _RequestsListScreenState();
}

class _RequestsListScreenState extends State<RequestsListScreen> {
  final _abdmService = AbdmService();
  bool _isLoading = true;
  String? _error;

  Map<String, dynamic>? _data;
  String _currentStatus = 'requested'; // requested, granted, denied
  final String _currentType = 'all';

  @override
  void initState() {
    super.initState();
    _fetchRequests();
  }

  Future<void> _fetchRequests() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final result = await _abdmService.getRequests(
        status: _currentStatus,
        type: _currentType,
      );
      setState(() => _data = result);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Requests & Subscriptions'),
        backgroundColor: Colors.blueGrey.shade900,
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          // Filters
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _currentStatus,
                    decoration: const InputDecoration(labelText: 'Status'),
                    items: const [
                      DropdownMenuItem(
                        value: 'requested',
                        child: Text('Running/Requested'),
                      ),
                      DropdownMenuItem(
                        value: 'granted',
                        child: Text('Granted'),
                      ),
                      DropdownMenuItem(value: 'denied', child: Text('Denied')),
                      DropdownMenuItem(
                        value: 'expired',
                        child: Text('Expired'),
                      ),
                    ],
                    onChanged: (val) {
                      if (val != null) {
                        setState(() => _currentStatus = val);
                        _fetchRequests();
                      }
                    },
                  ),
                ),
                const SizedBox(width: 16),
                IconButton(
                  icon: const Icon(Icons.refresh),
                  onPressed: _fetchRequests,
                ),
              ],
            ),
          ),

          Expanded(child: _buildContent()),
        ],
      ),
    );
  }

  Widget _buildContent() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'Error: $_error',
            style: const TextStyle(color: Colors.red),
          ),
        ),
      );
    }

    // Combine subscriptions and consents
    final subscriptions = _data?['subscriptions'] as List? ?? [];
    final consents = _data?['consents'] as List? ?? [];

    final allItems = [
      ...subscriptions,
      ...consents,
    ]; // Crude mix, better to separate sections

    if (allItems.isEmpty) {
      return const Center(child: Text('No requests found'));
    }

    return ListView(
      children: [
        if (subscriptions.isNotEmpty) ...[
          _buildSectionHeader('Subscriptions (${subscriptions.length})'),
          ...subscriptions.map(
            (s) => _buildRequestCard(s, isSubscription: true),
          ),
        ],
        if (consents.isNotEmpty) ...[
          _buildSectionHeader('Consents (${consents.length})'),
          ...consents.map((c) => _buildRequestCard(c, isSubscription: false)),
        ],
      ],
    );
  }

  Widget _buildSectionHeader(String title) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.grey.shade100,
      child: Text(
        title,
        style: const TextStyle(
          fontWeight: FontWeight.bold,
          color: Colors.blueGrey,
        ),
      ),
    );
  }

  Widget _buildRequestCard(
    Map<String, dynamic> item, {
    required bool isSubscription,
  }) {
    final id = item['id'] ?? 'Unknown ID';
    final date = item['created_at'] != null
        ? DateFormat('dd MMM yyyy').format(DateTime.parse(item['created_at']))
        : 'Unknown Date';
    final requester = item['requester']?['name'] ?? 'Unknown Requester';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: isSubscription
              ? Colors.purple.shade100
              : Colors.blue.shade100,
          child: Icon(
            isSubscription ? Icons.notifications_active : Icons.security,
            color: isSubscription ? Colors.purple : Colors.blue,
          ),
        ),
        title: Text(requester),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('ID: ${id.substring(0, 8)}...'),
            Text('Created: $date', style: const TextStyle(fontSize: 12)),
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          // TODO: Show details
        },
      ),
    );
  }
}

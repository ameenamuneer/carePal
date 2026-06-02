import 'package:flutter/material.dart';
import 'profile/abha_registration_screen.dart';
import 'profile/phr_onboarding_screen.dart';
import 'login_screen.dart';
import '../services/api_service.dart';

class AdminScreen extends StatelessWidget {
  const AdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Console'),
        backgroundColor: Colors.blueGrey.shade900,
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildAdminCard(
            context,
            title: 'Create Identity',
            subtitle: 'Register new ABHA/CarePal ID',
            icon: Icons.person_add,
            color: Colors.green,
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => const AbhaRegistrationScreen(),
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          _buildAdminCard(
            context,
            title: 'Link Records',
            subtitle: 'Discover and link health records (Requires Login)',
            icon: Icons.link,
            color: Colors.blue,
            onTap: () async {
              // Check if logged in
              final api = ApiService();
              final hasToken = await api.getAccessToken() != null;

              if (hasToken) {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const PhrOnboardingScreen(),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Please login first to link records'),
                  ),
                );
                // Optionally redirect to login
                Navigator.of(
                  context,
                ).push(MaterialPageRoute(builder: (_) => const LoginScreen()));
              }
            },
          ),
          const SizedBox(height: 16),
          _buildAdminCard(
            context,
            title: 'System Health',
            subtitle: 'Check API Connectivity',
            icon: Icons.dns,
            color: Colors.orange,
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Health check feature coming soon'),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildAdminCard(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: TextStyle(color: Colors.grey.shade600),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_ios, size: 16, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }
}

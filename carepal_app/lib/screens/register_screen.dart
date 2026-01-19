import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/app_colors.dart';
import '../providers/auth_provider.dart';
import 'dashboard_screen.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();

  // Controllers
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _firstNameController = TextEditingController();
  final _lastNameController = TextEditingController();
  final _dobController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  DateTime? _selectedDate;

  Future<void> _selectDate(BuildContext context) async {
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: DateTime(1990),
      firstDate: DateTime(1900),
      lastDate: DateTime.now(),
    );
    if (picked != null && picked != _selectedDate) {
      setState(() {
        _selectedDate = picked;
        _dobController.text =
            "${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}";
      });
    }
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;

    if (_passwordController.text != _confirmPasswordController.text) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Passwords do not match')));
      return;
    }

    final userData = {
      'username': _usernameController.text,
      'email': _emailController.text,
      'phone_number': _phoneController.text,
      'first_name': _firstNameController.text,
      'last_name': _lastNameController.text,
      'date_of_birth': _dobController.text,
      'password': _passwordController.text,
      'password_confirm': _confirmPasswordController.text,
      'user_type': 'PATIENT', // Defaulting to Patient
    };

    final provider = Provider.of<AuthProvider>(context, listen: false);
    final success = await provider.register(userData);

    if (success && mounted) {
      // Navigate to Dashboard (removes build stack history so user can't go back to register)
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const DashboardScreen()),
        (Route<dynamic> route) => false,
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.errorMessage ?? 'Registration Failed'),
          backgroundColor: AppColors.error,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Create Account'),
        backgroundColor: Colors.white,
        elevation: 0,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Form(
                key: _formKey,
                child: Column(
                  children: [
                    _buildSectionTitle('Personal Info'),
                    Row(
                      children: [
                        Expanded(
                          child: _buildTextField(
                            _firstNameController,
                            'First Name',
                            Icons.person,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: _buildTextField(
                            _lastNameController,
                            'Last Name',
                            Icons.person_outline,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    _buildTextField(
                      _dobController,
                      'Date of Birth (YYYY-MM-DD)',
                      Icons.calendar_today,
                      readOnly: true,
                      onTap: () => _selectDate(context),
                    ),

                    const SizedBox(height: 24),
                    _buildSectionTitle('Contact Details'),
                    _buildTextField(
                      _emailController,
                      'Email Address',
                      Icons.email,
                      type: TextInputType.emailAddress,
                    ),
                    const SizedBox(height: 16),
                    _buildTextField(
                      _phoneController,
                      'Phone Number',
                      Icons.phone,
                      type: TextInputType.phone,
                    ),

                    const SizedBox(height: 24),
                    _buildSectionTitle('Security'),
                    _buildTextField(
                      _usernameController,
                      'Username',
                      Icons.account_circle,
                    ),
                    const SizedBox(height: 16),
                    _buildTextField(
                      _passwordController,
                      'Password',
                      Icons.lock,
                      isPassword: true,
                    ),
                    const SizedBox(height: 16),
                    _buildTextField(
                      _confirmPasswordController,
                      'Confirm Password',
                      Icons.lock_outline,
                      isPassword: true,
                    ),

                    const SizedBox(height: 40),
                    Consumer<AuthProvider>(
                      builder: (context, auth, _) {
                        return SizedBox(
                          width: double.infinity,
                          child: auth.isLoading
                              ? const Center(child: CircularProgressIndicator())
                              : ElevatedButton(
                                  onPressed: _handleRegister,
                                  style: ElevatedButton.styleFrom(
                                    padding: const EdgeInsets.symmetric(
                                      vertical: 18,
                                    ),
                                  ),
                                  child: const Text('REGISTER'),
                                ),
                        );
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.only(bottom: 16),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.bold,
          color: AppColors.primary,
        ),
      ),
    );
  }

  Widget _buildTextField(
    TextEditingController controller,
    String label,
    IconData icon, {
    bool isPassword = false,
    TextInputType? type,
    bool readOnly = false,
    VoidCallback? onTap,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: isPassword,
      keyboardType: type,
      readOnly: readOnly,
      onTap: onTap,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 20),
      ),
      validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
    );
  }
}

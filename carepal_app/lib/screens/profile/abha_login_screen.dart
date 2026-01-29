import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/abdm_provider.dart';
import '../dashboard_screen.dart';

class AbhaLoginScreen extends StatefulWidget {
  const AbhaLoginScreen({Key? key}) : super(key: key);

  @override
  _AbhaLoginScreenState createState() => _AbhaLoginScreenState();
}

class _AbhaLoginScreenState extends State<AbhaLoginScreen> {
  int _currentStep = 0;
  final _mobileController = TextEditingController();
  final _otpController = TextEditingController();
  String? _selectedAbhaAddress;

  @override
  void dispose() {
    _mobileController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.green),
    );
  }

  Future<void> _submitMobile() async {
    final mobile = _mobileController.text.trim();
    if (mobile.length != 10) {
      _showError('Please enter a valid 10-digit Mobile number');
      return;
    }

    final provider = Provider.of<AbdmProvider>(context, listen: false);
    final success = await provider.initiateLogin(mobile);

    if (success) {
      _showSuccess('OTP Sent Successfully');
      setState(() {
        _currentStep = 1;
      });
    } else {
      if (provider.errorMessage != null) {
        _showError(provider.errorMessage!);
      }
    }
  }

  Future<void> _submitOtp() async {
    final otp = _otpController.text.trim();
    if (otp.length != 6) {
      _showError('Please enter a valid 6-digit OTP');
      return;
    }

    final provider = Provider.of<AbdmProvider>(context, listen: false);
    final success = await provider.verifyLogin(otp);

    if (success) {
      // Check skip_state to determine next action
      if (provider.skipState == 'abha_select' &&
          provider.abhaProfiles.isNotEmpty) {
        // Move to Step 3: ABHA selection
        setState(() {
          _currentStep = 2;
        });
      } else {
        // Login complete, go to dashboard
        _showSuccess(
          'Login Successful!\nWelcome ${provider.fullName ?? "User"}',
        );
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const DashboardScreen()),
          (route) => false,
        );
      }
    } else {
      if (provider.errorMessage != null) {
        _showError(provider.errorMessage!);
      }
    }
  }

  Future<void> _submitAbhaSelection() async {
    if (_selectedAbhaAddress == null) {
      _showError('Please select an ABHA address');
      return;
    }

    final provider = Provider.of<AbdmProvider>(context, listen: false);
    final success = await provider.completeLogin(_selectedAbhaAddress!);

    if (success) {
      _showSuccess('Login Successful!\nWelcome ${provider.fullName ?? "User"}');
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const DashboardScreen()),
        (route) => false,
      );
    } else {
      if (provider.errorMessage != null) {
        _showError(provider.errorMessage!);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<AbdmProvider>(context);
    final isLoading = provider.state == AbdmState.loading;

    return Scaffold(
      appBar: AppBar(title: const Text('ABHA Login')),
      body: Stepper(
        type: StepperType.vertical,
        currentStep: _currentStep,
        controlsBuilder: (context, details) {
          return const SizedBox.shrink();
        },
        steps: [
          Step(
            title: const Text('Mobile Login'),
            subtitle: const Text('Enter your 10-digit Mobile number'),
            isActive: _currentStep >= 0,
            state: _currentStep > 0 ? StepState.complete : StepState.indexed,
            content: Column(
              children: [
                TextField(
                  controller: _mobileController,
                  decoration: const InputDecoration(
                    labelText: 'Mobile Number',
                    border: OutlineInputBorder(),
                    hintText: '9876543210',
                  ),
                  keyboardType: TextInputType.phone,
                  maxLength: 10,
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: isLoading ? null : _submitMobile,
                  child: isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text('Send OTP'),
                ),
              ],
            ),
          ),
          Step(
            title: const Text('OTP Verification'),
            subtitle: const Text('Enter OTP sent to your mobile number'),
            isActive: _currentStep >= 1,
            state: _currentStep > 1 ? StepState.complete : StepState.indexed,
            content: Column(
              children: [
                if (provider.errorMessage != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Text(
                      provider.errorMessage!,
                      style: TextStyle(color: Colors.red),
                    ),
                  ),
                TextField(
                  controller: _otpController,
                  decoration: const InputDecoration(
                    labelText: 'OTP',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: isLoading ? null : _submitOtp,
                  child: isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text('Verify & Login'),
                ),
              ],
            ),
          ),
          Step(
            title: const Text('Select ABHA Address'),
            subtitle: const Text('Choose your ABHA address to login'),
            isActive: _currentStep >= 2,
            state: _currentStep > 2 ? StepState.complete : StepState.indexed,
            content: Column(
              children: [
                if (provider.abhaProfiles.isEmpty)
                  const Text('No ABHA addresses found')
                else
                  ...provider.abhaProfiles.map((profile) {
                    final abhaAddress = profile['abha_address'] ?? '';
                    final name = profile['name'] ?? 'Unknown';
                    final kycVerified = profile['kyc_verified'] == 'true';

                    return RadioListTile<String>(
                      title: Text(abhaAddress),
                      subtitle: Text(
                        '$name ${kycVerified ? "✓ Verified" : ""}',
                      ),
                      value: abhaAddress,
                      groupValue: _selectedAbhaAddress,
                      onChanged: (value) {
                        setState(() {
                          _selectedAbhaAddress = value;
                        });
                      },
                    );
                  }).toList(),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: isLoading ? null : _submitAbhaSelection,
                  child: isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text('Complete Login'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

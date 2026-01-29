import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/abdm_provider.dart';
import 'abha_login_screen.dart';

class AbhaRegistrationScreen extends StatefulWidget {
  const AbhaRegistrationScreen({Key? key}) : super(key: key);

  @override
  _AbhaRegistrationScreenState createState() => _AbhaRegistrationScreenState();
}

class _AbhaRegistrationScreenState extends State<AbhaRegistrationScreen> {
  int _currentStep = 0;
  final _mobileController = TextEditingController();
  final _otpController = TextEditingController();
  final _abhaAddressController = TextEditingController();

  @override
  void dispose() {
    _mobileController.dispose();
    _otpController.dispose();
    _abhaAddressController.dispose();
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
    final success = await provider.initiateRegistration(mobile);

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
    final success = await provider.verifyOtp(otp);

    if (success) {
      _showSuccess('OTP Verified');
      setState(() {
        _currentStep = 2;
      });
    } else {
      if (provider.errorMessage != null) {
        _showError(provider.errorMessage!);
      }
    }
  }

  Future<void> _createAbha() async {
    final address = _abhaAddressController.text.trim();
    if (address.isEmpty) {
      _showError('Please enter a preferred ABHA address');
      return;
    }

    final provider = Provider.of<AbdmProvider>(context, listen: false);
    final success = await provider.createAbhaAddress(address);

    if (success) {
      _showSuccess(
        'ABHA Created Successfully!\nABHA Number: ${provider.abhaNumber}',
      );
      Navigator.pop(context); // Go back to profile
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
      appBar: AppBar(
        title: const Text('Create ABHA ID'),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const AbhaLoginScreen(),
                ),
              );
            },
            child: const Text('Login', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
      body: Stepper(
        type: StepperType.vertical,
        currentStep: _currentStep,
        controlsBuilder: (context, details) {
          return const SizedBox.shrink();
        },
        steps: [
          Step(
            title: const Text('Mobile Verification'),
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
                      : const Text('Verify OTP'),
                ),
              ],
            ),
          ),
          Step(
            title: const Text('Create ABHA Address'),
            subtitle: const Text('Choose a unique username (e.g., name.123)'),
            isActive: _currentStep >= 2,
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
                  controller: _abhaAddressController,
                  decoration: const InputDecoration(
                    labelText: 'Preferred ABHA Address',
                    border: OutlineInputBorder(),
                    suffixText: '@abdm',
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: isLoading ? null : _createAbha,
                  child: isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text('Create ABHA ID'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

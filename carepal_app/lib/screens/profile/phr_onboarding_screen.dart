import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/app_colors.dart';
import '../../services/abdm/abdm_service.dart';

class PhrOnboardingScreen extends StatefulWidget {
  const PhrOnboardingScreen({super.key});

  @override
  State<PhrOnboardingScreen> createState() => _PhrOnboardingScreenState();
}

class _PhrOnboardingScreenState extends State<PhrOnboardingScreen> {
  final _mobileController = TextEditingController();
  final _otpController = TextEditingController();
  final _abdmService = AbdmService(); // Uses ApiService singleton

  int _currentStep = 0; // 0: Discover, 1: Select Records, 2: OTP, 3: Success
  bool _isLoading = false;
  String? _error;

  // Discovery Results
  String? _txnId;
  List<dynamic> _patientRecords = [];
  List<dynamic> _selectedContexts = [];
  Map<String, dynamic>? _selectedPatient;

  @override
  void dispose() {
    _mobileController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  // Step 1: Discover
  Future<void> _handleDiscover() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final result = await _abdmService.discoverCareContexts(
        hipId:
            '123456', // TODO: Get from Env or Config? User said 'carepal hip_id'
        refId: _mobileController.text.trim(),
      );

      setState(() {
        _txnId = result['txn_id'];
        final patients = result['patient'] as List?;
        if (patients != null && patients.isNotEmpty) {
          _patientRecords = patients;
          _currentStep = 1;
        } else {
          _error = 'No records found for this number.';
        }
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _isLoading = false);
    }
  }

  // Step 2: Initiate Link
  Future<void> _handleLinkInit() async {
    if (_selectedContexts.isEmpty || _selectedPatient == null) {
      setState(() => _error = 'Please select at least one record.');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final txnId = await _abdmService.initiateLinking(
        txnId: _txnId!,
        patient: _selectedPatient!,
        careContexts: _selectedContexts,
      );

      setState(() {
        _txnId = txnId; // Update txnId for next step
        _currentStep = 2; // Move to OTP
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _isLoading = false);
    }
  }

  // Step 3: Confirm Link
  Future<void> _handleLinkConfirm() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final success = await _abdmService.confirmLinking(
        txnId: _txnId!,
        otp: _otpController.text.trim(),
      );

      if (success) {
        setState(() => _currentStep = 3); // Success
      }
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
        title: const Text('Connect Health Records'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Progress Indicator
              Row(
                children: [
                  _buildStepIndicator(0, 'Discover'),
                  _buildStepLine(0),
                  _buildStepIndicator(1, 'Select'),
                  _buildStepLine(1),
                  _buildStepIndicator(2, 'Link'),
                ],
              ),
              const SizedBox(height: 32),

              if (_error != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  margin: const EdgeInsets.only(bottom: 24),
                  decoration: BoxDecoration(
                    color: AppColors.error.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    _error!,
                    style: TextStyle(color: AppColors.error),
                  ),
                ),

              // Steps
              if (_currentStep == 0) _buildDiscoverStep(),
              if (_currentStep == 1) _buildSelectionStep(),
              if (_currentStep == 2) _buildOtpStep(),
              if (_currentStep == 3) _buildSuccessStep(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStepIndicator(int stepIndex, String label) {
    final isActive = _currentStep >= stepIndex;
    return Column(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isActive ? AppColors.primary : Colors.grey.shade300,
          ),
          child: Center(
            child: Text(
              '${stepIndex + 1}',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: isActive ? AppColors.primary : Colors.grey,
            fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ],
    );
  }

  Widget _buildStepLine(int index) {
    return Expanded(
      child: Container(
        height: 2,
        color: _currentStep > index ? AppColors.primary : Colors.grey.shade300,
        margin: const EdgeInsets.only(bottom: 20),
      ),
    );
  }

  // Views for each step
  Widget _buildDiscoverStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Find Your Records',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        const Text(
          'Enter your mobile number registered with the hospital to find your records.',
          style: TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 24),
        TextField(
          controller: _mobileController,
          keyboardType: TextInputType.phone,
          decoration: InputDecoration(
            labelText: 'Mobile Number',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            prefixIcon: const Icon(Icons.phone),
          ),
        ),
        const SizedBox(height: 32),
        ElevatedButton(
          onPressed: _isLoading ? null : _handleDiscover,
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: _isLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2,
                  ),
                )
              : const Text('Discover Records'),
        ),
      ],
    );
  }

  Widget _buildSelectionStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Select Records',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        ..._patientRecords.map((patient) {
          final contexts = patient['care_contexts'] as List;
          return Card(
            margin: const EdgeInsets.only(bottom: 16),
            child: Column(
              children: [
                ListTile(
                  title: Text(patient['display'] ?? 'Unknown'),
                  subtitle: const Text('Patient Name'),
                  leading: const CircleAvatar(child: Icon(Icons.person)),
                ),
                const Divider(),
                ...contexts.map((ctx) {
                  final isSelected = _selectedContexts.any(
                    (c) => c['id'] == ctx['id'],
                  );
                  return CheckboxListTile(
                    value: isSelected,
                    title: Text(ctx['display'] ?? 'Record'),
                    onChanged: (val) {
                      setState(() {
                        if (val == true) {
                          _selectedContexts.add(ctx);
                          _selectedPatient =
                              patient; // Assumption: user selects from one patient
                        } else {
                          _selectedContexts.removeWhere(
                            (c) => c['id'] == ctx['id'],
                          );
                          if (_selectedContexts.isEmpty)
                            _selectedPatient = null;
                        }
                      });
                    },
                  );
                }),
              ],
            ),
          );
        }),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _isLoading ? null : _handleLinkInit,
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: _isLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2,
                  ),
                )
              : const Text('Link Selected Records'),
        ),
      ],
    );
  }

  Widget _buildOtpStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Verify OTP',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          'Enter the OTP sent to ${_mobileController.text}',
          style: const TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 24),
        TextField(
          controller: _otpController,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: 'OTP',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            prefixIcon: const Icon(Icons.lock_clock),
          ),
        ),
        const SizedBox(height: 32),
        ElevatedButton(
          onPressed: _isLoading ? null : _handleLinkConfirm,
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: _isLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2,
                  ),
                )
              : const Text('Confirm Link'),
        ),
      ],
    );
  }

  Widget _buildSuccessStep() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.check_circle, color: Colors.green, size: 80),
          const SizedBox(height: 24),
          const Text(
            'Records Linked Successfully!',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          const Text(
            'Your health records have been securely connected to your ABHA profile.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 32),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text('Go to Dashboard'),
          ),
        ],
      ),
    );
  }
}

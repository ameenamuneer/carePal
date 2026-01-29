import 'package:flutter/material.dart';
import '../services/abdm/abdm_service.dart';
import '../services/api_service.dart';

enum AbdmState { idle, loading, success, error }

class AbdmProvider with ChangeNotifier {
  final AbdmService _service = AbdmService();

  AbdmState _state = AbdmState.idle;
  String? _errorMessage;
  String? _txnId; // Stores transaction ID for multi-step flow

  // Registration Data
  String? _mobile;
  String? _abhaNumber;
  String? _abhaAddress;
  String? _fullName;

  // Login-specific data
  String? _skipState;
  List<Map<String, dynamic>> _abhaProfiles = [];

  // Getters
  AbdmState get state => _state;
  String? get errorMessage => _errorMessage;
  String? get txnId => _txnId;
  String? get abhaNumber => _abhaNumber;
  String? get abhaAddress => _abhaAddress;
  String? get fullName => _fullName;
  String? get skipState => _skipState;
  List<Map<String, dynamic>> get abhaProfiles => _abhaProfiles;

  // Step 1: Initiate Registration
  Future<bool> initiateRegistration(String mobile) async {
    _setLoading();
    try {
      _txnId = await _service.initiateRegistration(mobile);
      _mobile = mobile;
      _setSuccess();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    }
  }

  // Step 2: Verify OTP
  Future<bool> verifyOtp(String otp) async {
    if (_txnId == null) {
      _setError("Transaction ID missing. Please restart registration.");
      return false;
    }

    _setLoading();
    try {
      final result = await _service.verifyOtp(_txnId!, otp);
      // Update txnId if a new one is returned (rare but possible in some flows)
      if (result.containsKey('txn_id')) {
        _txnId = result['txn_id'];
      }

      _setSuccess();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    }
  }

  // Step 3: Create ABHA Address
  Future<bool> createAbhaAddress(String abhaAddress) async {
    if (_txnId == null) {
      _setError("Transaction ID missing.");
      return false;
    }

    _setLoading();
    try {
      final result = await _service.createAbhaAddress(_txnId!, abhaAddress);

      _abhaNumber = result['abha_number'];
      _abhaAddress = result['abha_address'];
      _fullName = result['full_name'];

      _setSuccess();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    }
  }

  // Helpers
  void _setLoading() {
    _state = AbdmState.loading;
    _errorMessage = null;
    notifyListeners();
  }

  void _setSuccess() {
    _state = AbdmState.success;
    _errorMessage = null;
    notifyListeners();
  }

  void _setError(String message) {
    _state = AbdmState.error;
    _errorMessage = message;
    notifyListeners();
  }

  void reset() {
    _state = AbdmState.idle;
    _errorMessage = null;
    _txnId = null;
    _mobile = null;
    _abhaNumber = null;
    _abhaAddress = null;
    _skipState = null;
    _abhaProfiles = [];
    notifyListeners();
  }

  // ==================== LOGIN FLOW ====================

  // Step 1: Initiate Login
  Future<bool> initiateLogin(String mobile) async {
    _setLoading();
    try {
      _txnId = await _service.initiateLogin(mobile);
      _mobile = mobile;
      _setSuccess();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    }
  }

  // Step 2: Verify Login OTP
  Future<bool> verifyLogin(String otp) async {
    if (_txnId == null) {
      _setError("Transaction ID missing. Please restart login.");
      return false;
    }

    _setLoading();
    try {
      final result = await _service.verifyLoginOtp(_txnId!, otp);

      // Update txnId if provided
      if (result.containsKey('txn_id')) {
        _txnId = result['txn_id'];
      }

      // Store skip_state and abha_profiles
      _skipState = result['skip_state'];
      if (result.containsKey('abha_profiles')) {
        _abhaProfiles = List<Map<String, dynamic>>.from(
          result['abha_profiles'],
        );
      }

      // If we got profile data, store it
      if (result.containsKey('profile')) {
        final profile = result['profile'];
        _abhaNumber = profile['abha_number'];
        _abhaAddress = profile['abha_address'];
        _fullName =
            '${profile['first_name'] ?? ''} ${profile['last_name'] ?? ''}'
                .trim();
      }

      // Check for tokens and save if present (Step 2 completion)
      if (result.containsKey('tokens') && result['tokens'] != null) {
        final tokens = result['tokens'];
        if (tokens['access'] != null && tokens['refresh'] != null) {
          await ApiService().saveTokens(tokens['access'], tokens['refresh']);
        }
      }

      _setSuccess();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    }
  }

  // Step 3: Complete Login (select ABHA address)
  Future<bool> completeLogin(String abhaAddress) async {
    if (_txnId == null) {
      _setError("Transaction ID missing.");
      return false;
    }

    _setLoading();
    try {
      final result = await _service.completeLogin(_txnId!, abhaAddress);

      // Store profile data
      if (result.containsKey('profile')) {
        final profile = result['profile'];
        _abhaNumber = result['abha_number'] ?? profile['abha_number'];
        _abhaAddress = abhaAddress;
        _fullName =
            '${profile['first_name'] ?? ''} ${profile['last_name'] ?? ''}'
                .trim();
      }

      // Check for tokens and save if present (Step 3 completion)
      if (result.containsKey('tokens') && result['tokens'] != null) {
        final tokens = result['tokens'];
        if (tokens['access'] != null && tokens['refresh'] != null) {
          await ApiService().saveTokens(tokens['access'], tokens['refresh']);
        }
      }

      _setSuccess();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    }
  }
}

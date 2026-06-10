import 'package:flutter/foundation.dart';
import '../models/patient_link.dart';
import '../services/link_service.dart';

class PatientProvider extends ChangeNotifier {
  final LinkService _service = LinkService();

  List<ClinicalRelationship> _clinicalLinks = [];
  List<FamilyMemberLink> _familyLinks = [];
  int? _activePatientId;
  String? _activePatientName;
  bool _isLoading = false;
  String? _error;

  List<ClinicalRelationship> get clinicalLinks => _clinicalLinks;
  List<FamilyMemberLink> get familyLinks => _familyLinks;
  int? get activePatientId => _activePatientId;
  String? get activePatientName => _activePatientName;
  bool get isLoading => _isLoading;
  String? get error => _error;

  /// Returns a unified list of patient IDs from either link type.
  List<int> get allPatientIds {
    final fromClinical = _clinicalLinks.map((e) => e.patient).toList();
    final fromFamily = _familyLinks.map((e) => e.patient).toList();
    return {...fromClinical, ...fromFamily}.toList();
  }

  bool get hasPatients => allPatientIds.isNotEmpty;

  /// Load all linked patients. Pass userType to decide which endpoint to call.
  Future<void> loadLinks(String userType) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      if (userType == 'DOCTOR') {
        _clinicalLinks = await _service.getMyPatients();
        _familyLinks = [];
        // Auto-select first patient if none selected
        if (_activePatientId == null && _clinicalLinks.isNotEmpty) {
          _activePatientId = _clinicalLinks.first.patient;
          _activePatientName = _clinicalLinks.first.patientName;
        }
      } else {
        _familyLinks = await _service.getMyFamilyLinks();
        _clinicalLinks = [];
        if (_activePatientId == null && _familyLinks.isNotEmpty) {
          _activePatientId = _familyLinks.first.patient;
          _activePatientName = _familyLinks.first.patientName;
        }
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void setActivePatient(int patientId, String name) {
    _activePatientId = patientId;
    _activePatientName = name;
    notifyListeners();
  }

  void clearActivePatient() {
    _activePatientId = null;
    _activePatientName = null;
    notifyListeners();
  }

  Future<void> addClinicalLink(ClinicalRelationship link) async {
    _clinicalLinks = [..._clinicalLinks, link];
    if (_activePatientId == null) {
      _activePatientId = link.patient;
      _activePatientName = link.patientName;
    }
    notifyListeners();
  }

  Future<void> addFamilyLink(FamilyMemberLink link) async {
    _familyLinks = [..._familyLinks, link];
    if (_activePatientId == null) {
      _activePatientId = link.patient;
      _activePatientName = link.patientName;
    }
    notifyListeners();
  }

  Future<void> removeClinicalLink(int relationshipId) async {
    _clinicalLinks =
        _clinicalLinks.where((l) => l.id != relationshipId).toList();
    _adjustActivePatient();
    notifyListeners();
  }

  Future<void> removeFamilyLink(int memberId) async {
    _familyLinks = _familyLinks.where((l) => l.id != memberId).toList();
    _adjustActivePatient();
    notifyListeners();
  }

  void _adjustActivePatient() {
    final ids = allPatientIds;
    if (!ids.contains(_activePatientId)) {
      if (ids.isNotEmpty) {
        if (_clinicalLinks.isNotEmpty) {
          _activePatientId = _clinicalLinks.first.patient;
          _activePatientName = _clinicalLinks.first.patientName;
        } else if (_familyLinks.isNotEmpty) {
          _activePatientId = _familyLinks.first.patient;
          _activePatientName = _familyLinks.first.patientName;
        }
      } else {
        _activePatientId = null;
        _activePatientName = null;
      }
    }
  }

  /// Returns true if the currently active patient has a ClinicalRelationship
  /// that grants the logged-in doctor medication edit rights.
  bool canEditMedicationsForActivePatient(String userType) {
    if (userType != 'DOCTOR') return false;
    final link = _clinicalLinks
        .where((l) => l.patient == _activePatientId)
        .firstOrNull;
    return link?.canEditMedications ?? false;
  }

  /// Wipe all state — call this on logout or before a new session starts.
  void clear() {
    _clinicalLinks = [];
    _familyLinks = [];
    _activePatientId = null;
    _activePatientName = null;
    _isLoading = false;
    _error = null;
    notifyListeners();
  }
}

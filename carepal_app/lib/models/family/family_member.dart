class FamilyMember {
  final int id;
  final String userName;
  final String userEmail;
  final String? userPhone;
  final String relationship;
  final String accessLevel;
  final bool isActive;
  final String? invitedByName;

  FamilyMember({
    required this.id,
    required this.userName,
    required this.userEmail,
    this.userPhone,
    required this.relationship,
    required this.accessLevel,
    required this.isActive,
    this.invitedByName,
  });

  factory FamilyMember.fromJson(Map<String, dynamic> json) {
    return FamilyMember(
      id: json['id'],
      userName: json['user_name'] ?? 'Unknown',
      userEmail: json['user_email'] ?? '',
      userPhone: json['user_phone'],
      relationship: json['relationship'] ?? 'Other',
      accessLevel: json['access_level'] ?? 'Basic',
      isActive: json['is_active'] ?? true,
      invitedByName: json['invited_by_name'],
    );
  }
}

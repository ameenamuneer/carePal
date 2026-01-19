class FamilyInvitation {
  final int id;
  final String inviteeEmail;
  final String? inviteeName;
  final String status; // PENDING, ACCEPTED, DECLINED, EXPIRED
  final String relationship;
  final String accessLevel;
  final DateTime createdAt;
  final DateTime expiresAt;

  FamilyInvitation({
    required this.id,
    required this.inviteeEmail,
    this.inviteeName,
    required this.status,
    required this.relationship,
    required this.accessLevel,
    required this.createdAt,
    required this.expiresAt,
  });

  factory FamilyInvitation.fromJson(Map<String, dynamic> json) {
    return FamilyInvitation(
      id: json['id'],
      inviteeEmail: json['invitee_email'],
      inviteeName: json['invitee_name'],
      status: json['status'],
      relationship: json['relationship'],
      accessLevel: json['access_level'],
      createdAt: DateTime.parse(json['created_at']),
      expiresAt: DateTime.parse(json['expires_at']),
    );
  }

  bool get isExpired => DateTime.now().isAfter(expiresAt);
}

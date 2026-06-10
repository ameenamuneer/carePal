class AppUser {
  final int id;
  final String username;
  final String email;
  final String firstName;
  final String lastName;
  final String userType; // DOCTOR, FAMILY
  final String? phoneNumber;

  AppUser({
    required this.id,
    required this.username,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.userType,
    this.phoneNumber,
  });

  String get fullName => '$firstName $lastName'.trim();

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: json['id'],
      username: json['username'] ?? '',
      email: json['email'] ?? '',
      firstName: json['first_name'] ?? '',
      lastName: json['last_name'] ?? '',
      userType: json['user_type'] ?? 'FAMILY',
      phoneNumber: json['phone_number'],
    );
  }
}

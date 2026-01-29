import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/medication_provider.dart';

class ImportPrescriptionScreen extends StatefulWidget {
  const ImportPrescriptionScreen({Key? key}) : super(key: key);

  @override
  _ImportPrescriptionScreenState createState() =>
      _ImportPrescriptionScreenState();
}

class _ImportPrescriptionScreenState extends State<ImportPrescriptionScreen> {
  final _prescriptionIdController = TextEditingController();

  @override
  void dispose() {
    _prescriptionIdController.dispose();
    super.dispose();
  }

  void _importPrescription() async {
    final id = _prescriptionIdController.text.trim();
    if (id.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a Prescription ID')),
      );
      return;
    }

    final provider = Provider.of<MedicationProvider>(context, listen: false);
    final count = await provider.importPrescription(id);

    if (count > 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Successfully imported $count medications')),
      );
      Navigator.pop(context);
    } else if (provider.error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Import Failed: ${provider.error}')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No medications found in this prescription'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<MedicationProvider>(context);
    final isLoading = provider.isLoading;

    return Scaffold(
      appBar: AppBar(title: const Text('Import from Eka.Care')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Enter the Prescription ID from your doctor or Eka.Care app to automatically import your medications.',
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _prescriptionIdController,
              decoration: const InputDecoration(
                labelText: 'Eka.Care Prescription ID',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.receipt_long),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: isLoading ? null : _importPrescription,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : const Text('Import Medications'),
            ),
          ],
        ),
      ),
    );
  }
}

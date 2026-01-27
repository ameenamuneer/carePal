allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}

subprojects {
    val project = this
    fun configureNamespace() {
        val android = project.extensions.findByName("android")
        if (android != null) {
            val baseExt = android as com.android.build.gradle.BaseExtension
            if (baseExt.namespace == null) {
                val groupName = if (project.group.toString().isNotEmpty()) project.group.toString() else "com.example.carepal"
                baseExt.namespace = "$groupName.${project.name.replace("-", "_")}"
            }
        }
    }

    if (project.state.executed) {
        configureNamespace()
    } else {
        project.afterEvaluate {
            configureNamespace()
        }
    }
}

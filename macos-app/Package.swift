// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MessageRefiner",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "RefinerMenu", targets: ["MenuBarApp"])
    ],
    targets: [
        .target(name: "RefinerCore"),
        .executableTarget(
            name: "MenuBarApp",
            dependencies: ["RefinerCore"],
            resources: [
                .copy("Resources/Fonts")
            ]
        ),
        .executableTarget(
            name: "RefinerTests",
            dependencies: ["RefinerCore"]
        ),
    ],
    swiftLanguageModes: [.v5]
)

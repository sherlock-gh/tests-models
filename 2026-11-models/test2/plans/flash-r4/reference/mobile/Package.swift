// swift-tools-version: 6.1
import PackageDescription
let package = Package(name: "CleaningLogic", platforms: [.macOS(.v13)], products: [.library(name: "CleaningLogic", targets: ["CleaningLogic"])], targets: [.target(name: "CleaningLogic", path: "Sources/CleaningLogic"), .testTarget(name: "CleaningLogicTests", dependencies: ["CleaningLogic"], path: "Tests/CleaningLogicTests")])

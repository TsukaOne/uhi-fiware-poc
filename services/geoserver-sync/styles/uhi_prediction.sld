<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>uhi_prediction</Name>
    <UserStyle>
      <Name>uhi_prediction_style</Name>
      <Title>Urban Heat Island Prediction (RdYlBu)</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <!-- Froid (Bleu) -->
              <ColorMapEntry color="#313695" quantity="0"   opacity="1" label="Very Cold"/>
              <ColorMapEntry color="#4575b4" quantity="50"  opacity="1"/>
              <ColorMapEntry color="#74add1" quantity="90"  opacity="1"/>
              <!-- Transition -->
              <ColorMapEntry color="#abd9e9" quantity="110" opacity="1"/>
              <ColorMapEntry color="#ffffbf" quantity="127" opacity="1" label="Neutral"/>
              <!-- Chaud -->
              <ColorMapEntry color="#fdae61" quantity="160" opacity="1"/>
              <ColorMapEntry color="#f46d43" quantity="190" opacity="1"/>
              <ColorMapEntry color="#d73027" quantity="220" opacity="1"/>
              <ColorMapEntry color="#a50026" quantity="254" opacity="1" label="Very Hot"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
